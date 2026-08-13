# ProofPrint

Drop in any image and learn everything knowable about it — who made it, whether it was edited, and if it's a stripped copy of something we sealed. Built on Genblaze \+ Backblaze B2 Object Lock.

[https://www.youtube.com/watch?v=\_\_0feH9nfZc](https://www.youtube.com/watch?v=__0feH9nfZc)

### Inspiration

On 2 August 2026 — two days before this submission — EU AI Act Article 50 became applicable. It requires providers of generative AI to mark synthetic images, audio and video in a machine-readable format. Almost no production stack does this today.

But the deeper problem showed up when we looked at how images actually move. A picture gets generated, downloaded, dropped into Slack, pulled into a CMS, re-exported twice, forwarded through WhatsApp. Every step destroys evidence. By the time someone asks "what made this, and has it been changed?", the honest answer is usually "we don't know."

The tools being built for this share one blind spot: they only recognise their own output. Hand them a file from anywhere else and they shrug. That felt backwards. The image you actually need to interrogate is almost never the one you generated yourself — it's the one someone just sent you.

So we built the inspector we wanted: drop in any image and get every signal that can be recovered from it.

### What it does

Inspect anything. Drag in a file, or paste a URL from anywhere on the web. ProofPrint returns one of five verdicts, and the reasoning behind each:

| VERDICT | MEANING |
| :---- | :---- |
| AUTHENTIC | Sealed by us and byte-identical to the immutable B2 record |
| MODIFIED | Our manifest is intact, but the pixels changed after sealing |
| TAMPERED | The provenance record itself was edited |
| STRIPPED\_COPY | No manifest survives, but it perceptually matches a sealed asset |
| EXTERNAL\_PROVENANCE | Not ours, but it carries C2PA Content Credentials |

Four independent evidence sources feed those verdicts:

1. Embedded Genblaze manifests. Sealed *inside* the PNG (iTXt), not as a sidecar that gets lost on the first re-upload. Editing the recorded prompt or model breaks the canonical SHA-256 hash.  
2. Byte-level anchoring. The reference digest is written to Backblaze B2 under Object Lock before the file ever leaves the pipeline. Forging a pass means rewriting a record that cannot be rewritten.  
3. Perceptual matching. A 64-bit difference hash tracks composition rather than encoding. We took a sealed 419 KB PNG, halved its resolution, re-encoded it to a 12 KB JPEG and destroyed every byte of metadata — a 34× reduction — and it still resolved to the exact run that produced it, at 0/64 bits difference. No hash-based verifier can do that.  
4. C2PA \+ EXIF forensics. We read Content Credentials from *other* issuers — DALL·E, Firefly, Photoshop, C2PA cameras — including the algorithmicMedia marker that denotes AI generation. And we surface what the file itself carries: camera make and model, lens, capture settings, GPS coordinates with a map link, editing software, XMP edit history, and the parameter blocks image generators leave behind.

Generate with provenance. A multi-provider Genblaze pipeline expands a brief, generates on open-weight models, seals the manifest into the file, and writes everything to B2 immutably. Iterate on any asset and the certificate renders the full v1 → v2 → v3 lineage.

Watch the archive. Live B2 stats: bytes under management, Object Lock coverage, per-provider split, and near-duplicate clustering that finds visually identical assets content-addressing can't deduplicate because their bytes genuinely differ.

### How we built it

FastAPI \+ Genblaze, with Backblaze B2 as the only datastore — there is no database.

Reliability is three tiers deep. Gemini expands the brief, walking a list of chat models because Google keeps closing older ones to new API keys. NVIDIA NIM generates on FLUX.1-dev with Genblaze's native fallback\_modelschain. If the entire NVIDIA leg dies, the mint re-runs on another provider — Genblaze's uniform Pipeline API is what makes that a provider swap instead of a rewrite. Every attempt, including failures and their latencies, is shown in the UI.

We wrote a Genblaze connector. Every first-party adapter needs an API key, which makes a failover leg only as available as its billing. Pollinations serves open-weight models over a keyless HTTP GET, so we implemented it against Genblaze's SyncProvider contract. It drops into Pipeline.step() like any built-in and lands in the same provenance manifest.

B2 does real work. Object Lock (GOVERNANCE) on sealed assets, manifests and ledger records. CONTENT\_ADDRESSABLE keying so the storage path *is* an integrity claim. An append-only ledger of one immutable object per mint, so concurrent mints can never clobber each other. Presigned URLs so B2 serves the bytes directly.

### Challenges we ran into

The SDK's shipped behaviour differed from its docs in ways that only appear live. Pipeline.run() doesn't raise on step failure by default — it returns a success-shaped result with status='failed' inside. Our cross-provider failover silently never fired, because a dead provider looked like success right up until asset extraction. PipelineResult.failed\_steps is a method, not a property, so the obvious check was truthy on a bound method. ListPage exposes .entries, not .objects, so our B2 ledger scan returned nothing and every verification reported "unknown origin."

Provider availability isn't what the model list says. FLUX.1-schnell hangs indefinitely on a fresh NVIDIA account because its NVCF function isn't provisioned; the Stable Diffusion endpoints 404 outright. Gemini's free tier grants exactly zero image quota. We found FLUX.1-dev by probing endpoints directly and reading a 422 that told us stepsmust be ≥ 5\.

Genblaze's JPEG handler hangs on real provider output. JpegHandler.extract() never returns on NVIDIA-sized JPEGs. We normalise sealed stills to PNG — lossless, so we're not degrading the asset we're certifying — and bounded every extraction with a deadline on a daemon thread, because ThreadPoolExecutor workers are non-daemon and one wedged extraction would hang shutdown and leak a thread per request.

Storage performance was a correctness problem in disguise. One immutable object per ledger record meant a verification issued a B2 GET per record, three times over. Cold scans took over five minutes and looked like hangs. Fixed with a short TTL cache invalidated on write, parallel fetches capped below botocore's connection pool, a retry for B2's mid-stream resets, and a background warm at startup.

### Accomplishments that we're proud of

Recovering provenance from a file that has none. Everything else here is careful engineering; the perceptual match is the part that felt like magic — watching a 12 KB WhatsApp-mangled JPEG resolve to the exact run that produced its 419 KB original.

Making Object Lock a real trust anchor rather than a checkbox, and probing it at startup so a bucket without it degrades honestly instead of failing a mint half-way through.

Being straight about limits. UNSIGNED means *"no provenance found"* — never *"this isn't AI."* Our manifests are hash-protected, not PKI-signed. EXIF is reported as observations, never evidence, and the UI says so. A verification tool that overclaims is worse than none.

### What we learned

Read the shipped source, not the docs. Every real bug we hit was a gap between what the SDK documented and what it did, and each one was invisible until we ran it against live providers.

Free tiers advertise more than they provision. Probe before you architect.

The interesting design question wasn't "is this authentic" — it was "how many different ways can provenance break, and does each one deserve a different answer?" That question produced the five-verdict taxonomy, and it's what separates this from a boolean.

### What's next for ProofPrint

PKI signing so verification doesn't require trusting our ledger. Video, using the same MP4 uuid\-box path Genblaze already supports. Writing C2PA rather than only reading it. Batch inspection for newsroom-scale archives. And upstreaming the Pollinations connector to Genblaze — a keyless provider is genuinely useful to anyone building failover.

## Built With

* alpinejs  
* backblaze-b2  
* boto3  
* c2pa  
* [docker](https://devpost.com/software/built-with/docker)  
* exif  
* fastapi  
* [flux](https://devpost.com/software/built-with/flux)  
* genblaze  
* google-gemini  
* nvidia-nim  
* object-lock  
* perceptual-hashing  
* pillow  
* pollinations  
* provenance  
* [python](https://devpost.com/software/built-with/python)  
* render  
* s3  
* sha-256  
* tailwindcss

