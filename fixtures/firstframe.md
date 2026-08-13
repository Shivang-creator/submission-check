# FirstFrame

Maya waits sixty-five seconds to watch four seconds of video and say no.
FirstFrame gets her to that same no in 9.3 seconds versus 65.7 seconds, measured on job `j_47cdc2`.
No account, no key, no card — no API key is required, so open the live URL and reproduce it now.

**Repo:** https://github.com/firstframe/firstframe ·
**Live:** https://firstframe.live ·
**Demo video:** https://youtu.be/8Qm2ZrK1x0A (2:41)

## The person we built it for

Maya storyboards ads. She types a prompt, hits generate, and waits. Sixty-five
seconds later four seconds of video appear, she watches them, and she says no —
the camera pushes in when she wanted it locked off. Then she edits three words
and waits sixty-five seconds again. On a normal afternoon she does this thirty
or forty times. She is not waiting to see a finished video. She is waiting for
permission to reject one.

That is what the 9.3 seconds buys: she reaches the same no while the old
pipeline is still on frame two. Job `j_47cdc2` is in the live log, and you can
replay it.

## What it does

FirstFrame streams the composition decision before the video exists.

It renders the model's first frame at full resolution as soon as the diffusion
pass for frame 0 completes, then shows the camera path as a vector overlay from
the motion conditioning — before a single subsequent frame is denoised. If the
framing is wrong, you kill the job and re-prompt. If it's right, the render
continues into the same job with no restart.

- **9.3s** to a decidable first frame, versus **65.7s** to the full four-second
  clip. Both on job `j_47cdc2`, same prompt, same model, same GPU class.
- **86%** of jobs in our own use are killed before frame 12, which is where the
  saving comes from: you pay for a seventh of the compute on the rejects.
- Kill-and-re-prompt keeps the seed, so the second attempt differs by your edit
  and nothing else.

## How we built it

A Modal worker holds the diffusion loop open and publishes a frame-0 tensor to
a Redis stream the moment it's denoised; the browser gets it over SSE. The
camera overlay is read out of the motion-conditioning tensor directly rather
than inferred from output frames, which is why it can be drawn before those
frames exist.

The cancel path is the load-bearing part. A kill has to stop billed GPU work,
not just close the socket, so cancellation is a token checked between denoise
steps and the worker exits the loop mid-job. We assert on the exit, not on the
UI: the test issues a kill at step 4 and asserts the worker recorded a
`CANCELLED_AT_STEP` value below 12 and released the GPU lease.

**358 executable assertions** run on every push, in 71 seconds, no GPU required
— the diffusion worker is faked at the tensor boundary so the orchestration,
cancellation, billing, and streaming paths are all exercised for real. The
suite includes the failure cases, not only the happy path.

We also attack our own guarantee rather than asserting it. We claim a killed
job stops billing; the test suite starts a real job, kills it, and then asserts
the meter is frozen by reading the billing ledger 30 seconds later and
requiring the same value. And we claim rendered outputs are immutable once
sealed: the test issues a real delete against the sealed object and asserts the
storage layer refuses it, with the refusal captured in the test output.

## What is broken right now

We are keeping this visible rather than hiding it, because you will hit it:

- Prompts over 340 characters make the camera overlay drift from the eventual
  render. The overlay renders with an `UNRELIABLE` badge above that length
  instead of quietly lying. One of our demo prompts trips it on purpose.
- Two of the 358 assertions are marked `KNOWN FAULT` and are visible in the CI
  output: multi-shot prompts report the first shot's camera path for the whole
  clip. We know why, we have not fixed it.
- Cold start on the first job of the day is about 40 seconds of Modal container
  boot, which is not included in the 9.3s number and should not be.

## Upstream

Building this surfaced real bugs in the tooling under us: **three pull requests
and an issue sent upstream**, each with a reproduction and a failing test.

- `modal-client` #2214 — cancellation token not propagated to child spawns, so
  killed jobs kept a GPU lease. Merged.
- `modal-client` #2219 — `Function.spawn()` leaks the call ID on timeout. Open,
  maintainer reviewed.
- `sse-starlette` #118 — flush ordering drops the final event when the client
  disconnects mid-stream. Merged.
- `diffusers` #9873 (issue) — `callback_on_step_end` fires after the VAE decode
  rather than after the denoise step, which makes true per-step early exit
  impossible without patching. Reproduction attached, no fix yet.

## Who this is for, today

Storyboard and previz teams at ad agencies and game studios — people who
generate dozens of throwaway clips per session and reject most of them. That's
Maya, and there are about forty of her in the two studios that have been using
this for a week. The live URL is open to anyone: no account, no key, no card.

## What's next

Per-shot overlays for multi-shot prompts (the known fault above), a self-hosted
worker image so studios can run it on their own GPUs, and an editor plugin so
the reject-and-re-prompt loop happens where the storyboard already lives.
