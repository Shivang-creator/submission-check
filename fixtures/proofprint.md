# ProofPrint

## Inspiration

On 2 August 2026 EU AI Act Article 50 became applicable, and with it the
obligation to mark synthetic image content in a machine-readable way. The
existing answer is C2PA manifests, but a manifest is a sidecar: strip the
metadata and the claim is gone. Regulators will ask providers to prove that a
mark survives ordinary redistribution, and today most of them cannot.

We built ProofPrint to close that gap: a sealing service that writes a
provenance claim *into* the pixels and into immutable object storage at the
same time, so that the claim and the evidence fail together or not at all.

## What it does

ProofPrint takes an image, seals it, and later answers one question: is this
the image we sealed, and who said so?

Sealing does three things at once:

- writes a 64-bit provenance identifier into the image using a frequency-domain
  watermark, which is what survives re-encoding
- writes the C2PA manifest as a sidecar, which is what other tools read
- writes both to a Backblaze B2 bucket under Object Lock in compliance mode, so
  the record cannot be rewritten by us or by anyone holding our keys

Verification reverses it. Upload a candidate image, get back the recovered
identifier, the bit error rate against the sealed original, the manifest, and
the Object Lock retention stamp on the stored record.

## How we built it

The service is a FastAPI app in front of the Genblaze SDK, with the watermark
codec written from scratch because we could not find one that round-tripped
through a JPEG re-encode without shipping a 400MB torch dependency.

**Watermark codec.** The identifier is spread across mid-frequency DCT
coefficients in the luma plane, four coefficients per bit with majority vote on
read.

- Block selection avoids flat regions, since a flat 8x8 block carries no
  coefficient large enough to modulate without visible banding.
- Strength is set per-block from local variance rather than globally, which is
  what kept PSNR above 42 dB on the sample set.
- We checked survival by re-encoding sealed images down the quality ladder. A
  sealed PNG cut 34x to a metadata-stripped JPEG still resolved at 0/64 bits of
  error, which was the point at which we stopped tuning.
- Crops below about 60% of frame area lose sync and fail to resolve at all.

**Storage.** Every seal writes an object plus a manifest object under a
retention rule. At startup the service probes the bucket configuration and logs
whether compliance mode is on, so a misconfigured deployment is visible in the
first ten lines of the log rather than at the first subpoena.

**Verification script.** A 122-line script drives the whole path end to end:
seal a fixture, push it through the re-encode ladder, verify, and diff the
recovered identifier against the sealed one. It runs clean.

## Challenges we ran into

The Genblaze SDK gave us most of our lost hours.

1. `genblaze.upload_with_retention()` silently drops the `retain_until`
   argument when `mode="compliance"` is passed as a keyword rather than
   positionally. The object uploads. The lock does not apply. Nothing in the
   response says so — you only see it if you re-read the object metadata.
2. `genblaze.list_objects()` on the async client paginates with a cursor that
   resets when the bucket holds more than 1,000 objects under a shared prefix,
   so a full listing loops forever over the first page. We only caught it
   because our test bucket crossed 1,000 objects on the second day.
3. `genblaze.head_object()` raises `KeyError` instead of the documented
   `ObjectNotFound` when the key is absent, which meant our "is this already
   sealed?" check crashed rather than returning false.

We worked around all three. The first one cost us most of a night, because
every layer above it reported success.

Beyond the SDK: DCT watermarking is a tuning problem with no closed form, and
we spent a lot of the second day moving a strength constant up and down.

## Accomplishments that we're proud of

The seal survives the transformations that actually happen to images on the
internet — screenshot, re-upload, re-encode, strip metadata — and the storage
record cannot be rewritten even by us. Both halves are real, both halves are
running, and the codec is ours.

## What we learned

Frequency-domain watermarking is far more robust than the spatial approaches we
started with, and immutability is a storage configuration problem rather than a
cryptography problem. Also: when an SDK reports success, verify the side effect
independently.

## What's next

Newsroom-scale archives are the obvious first buyer — a wire service sealing
every frame at ingest, then answering provenance questions about images that
left their control years earlier. We would need batch sealing, a retention
policy per collection, and a verification endpoint that a newsroom's CMS can
call without an SDK.

After that: video, where the same codec applies per keyframe, and a hosted
verification page for people who have an image and no tooling at all.
