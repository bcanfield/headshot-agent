# AI LinkedIn headshot from ordinary photos: options, privacy terms, recommendation

Research notes, dated 2026-11-23. Prices, policies and model names change; verify before relying on them.

Research only; no photos were opened or uploaded.

Method note: pages were read with a fetch tool that returns a model-written extract of the page, not raw text, and some facts came from search-result summaries. Items marked **(secondhand)** or **(unverified)** were not confirmed on the owner's page. Prices and policies change often, so re-check before paying. Marketing pages are the owner's own statements, not independent evidence of quality.

## 1. LinkedIn rules (read this first)

- **Size and format.** Photo must be PNG or JPG (no GIF), max 8 MB, between 400x400 and 7680x4320 px; the help page suggests a photo that needs little cropping. [LinkedIn Help: photo won't upload](https://www.linkedin.com/help/linkedin/answer/a549049) (this page's own "recommended 400x400" wording was only seen in a search summary, **secondhand**). Background banner: 1584x396 (same page).
- **Likeness rule.** "You can use an illustration, caricature, or other artistic rendering of yourself," but "your profile photo must reflect your likeness." LinkedIn may remove photos that break its User Agreement or Professional Community Policies, and lists others' likenesses (stock, celebrities, fictional characters) as non-compliant. The page does not mention AI-generated or altered photos at all. [Profile photo guidelines](https://www.linkedin.com/help/linkedin/answer/a1377087/profile-photo-guidelines-and-conditions)
- **Community Policies.** "Do not use an image of someone else, or any other image that is not your likeness, for your profile photo"; no fake profiles; no misleading information about yourself. No AI-photo-specific rule; the synthetic-media rule covers media depicting a person saying something they did not say, unless disclosed. [Professional Community Policies](https://www.linkedin.com/legal/professional-community-policies)
- **Detection.** LinkedIn says it runs a model that checks profile photo uploads for AI generation, without facial recognition, aimed at fake accounts. [LinkedIn Trust & Safety, 2022-10-25](https://www.linkedin.com/blog/member/trust-and-safety/new-linkedin-profile-features-help-verify-identity-detect-remove-fake-accounts-boost-authenticity). Inference (mine): a heavily stylized or beautified image that doesn't look like you is both a rules risk and a detection risk; a faithful, lightly edited one is the safe side. LinkedIn's help text gives no explicit allow/deny for AI headshots.
- **LinkedIn's own tips.** Crop from top of shoulders to just above the head, face about 60% of frame, simple background, smile, recent (within the past few years) and how you look day to day. The tips page does not mention AI. [LinkedIn Talent blog](https://www.linkedin.com/business/talent/blog/product-tips/tips-for-picking-the-right-linkedin-profile-picture)

## 2. Hosted "AI headshot" services

All figures from each vendor's own pages, checked 2026-11-23.

| Service | Price (one-time) | Output / turnaround | Input photos |
|---|---|---|---|
| [HeadshotPro](https://www.headshotpro.com/pricing) | $29 / $39 / $59 | 30 / 50 / 70 headshots; ~2 h / ~30 min / ~15 min | Docs say 2-3 selfies plus optional full-body ([docs](https://www.headshotpro.com/docs/individual/getting-started/overview)); pricing page says "a few selfies" |
| [Aragon](https://www.aragon.ai/pricing) | $35 / $45 / $75 (listed with a 20% promo) | 40 / 60 / 100 headshots; 45 / 30 / 15 min | Pricing page does not say. Blog says "a few photos", varied angles, good light, no heavy filters ([blog](https://www.aragon.ai/blog/how-to-get-ai-headshot)); another page reportedly says at least 6 (**secondhand**) |
| [BetterPic](https://www.betterpic.io/pricing) | $35 / $39 / $79; free tier up to 10 | 20 / 60 / 120 headshots; 2 h / 1.5 h / 1 h | Pricing page does not say |

### Data terms

- **HeadshotPro.** Security page: "Uploaded photos are deleted 30 days after your headshots are generated"; "never used to train, fine-tune, or improve any AI model"; no personal AI model is built from a face or kept after the session; account deletion removes personal data within 14 days; you can delete photos any time. [Security](https://www.headshotpro.com/security). Results auto-delete after 30 days (download first) ([docs](https://www.headshotpro.com/docs/individual/getting-started/overview)). The formal privacy policy (Last Updated 10/22/2026) does not address uploaded photos or training at all, so the strong claims live on marketing/security pages, not in the policy. [Privacy](https://www.headshotpro.com/privacy). Subprocessor list is at /legal/sub-processors (not read).
- **Aragon.** Policy: face data permanently deleted or anonymized within 30 days after the earliest of content delivery (except active subscribers), account closure, deletion request, or one year from collection. Face data not used to train its own models; AI vendors are contractually barred from using it to train generalized models; no sale of face data. But it also shares identifiers with advertising partners and public gallery content may be visible to others. No effective date shown. [Privacy](https://www.aragon.ai/privacy)
- **BetterPic.** Privacy policy (updated Oct 8, 2025), section 8.2: **input photos stored up to 1 year**, trained AI models up to 3 years, output photos up to 3 years, instant deletion on request via UI or support; account data deleted within 90 days of account deletion; primary storage EU (Frankfurt). [Privacy policy (fetched via scrapling)](https://www.betterpic.io/legal/privacy-policy). BetterPic's marketing pages reportedly say 30 days and no general-model training, and its free tier may allow marketing use; those pages conflict with the policy and were seen only in a search summary (**secondhand**), e.g. [BetterPic blog](https://www.betterpic.io/blog/are-ai-headshots-safe). Where they differ, the policy is the binding text.

Takeaway: on the stated terms, HeadshotPro and Aragon are tighter on retention than BetterPic; none can be audited from outside.

## 3. Fine-tune your own identity model via API (LoRA)

Provider pages I could read are FLUX.1-era (2025); I did not find a current identity-specific trainer for newer models.

- **Replicate, ostris/flux-dev-lora-trainer.** Zip of images; as few as 2 work, "10 images is a good minimum"; 1024x1024 or higher if possible; JPG/PNG/WebP; filenames and aspect ratio don't matter; unique trigger word (not a real word, not `TOK`); keep 1000 steps. Cost on the docs' example: 8x H100 at $0.0122/s, about 2 minutes, about $1.46. Run the result via web or API, include the trigger word in the prompt. [Replicate docs](https://replicate.com/docs/get-started/fine-tune-with-flux). Face-specific blog: at least 10 images, "Variety is key" (settings, clothing, lighting, angles), about $1.85 for a ~20-minute run (older hardware pricing, conflicts with the docs figure). [Replicate blog](https://replicate.com/blog/fine-tune-flux-with-faces)
- **Replicate, replicate/fast-flux-trainer.** 10-20 images, around 1024x1024, optional per-image `.txt` captions (else autocaption with trigger word), subject vs style mode. Character tips: vary settings, expressions and backgrounds; keep haircut and apparent age consistent; avoid frequent hands-near-face. Via API the zip must be hosted at a URL. No price on the page. [README](https://replicate.com/replicate/fast-flux-trainer/readme)
- **fal, flux-lora-portrait-trainer.** Zip of at least 10 images, optional captions with `[trigger]` placeholder, `trigger_phrase`, default 2500 steps, `subject_crop` default true; outputs a diffusers LoRA plus config. Price not on the page; about $2.40 per 1000 steps appeared in a search summary of its llms.txt (**secondhand**). [fal docs](https://fal.ai/models/fal-ai/flux-lora-portrait-trainer/api)
- **fal, flux-lora-fast-training.** Required `images_data_url` zip; "at least 4 images"; optional trigger word and captions. [fal docs](https://fal.ai/models/fal-ai/flux-lora-fast-training/api). FLUX.2 trainers also exist on fal (`flux-2-trainer`, `flux-2-trainer-v2`) with conflicting per-step prices across pages (**unverified**): [FLUX 2 Trainer](https://fal.ai/models/fal-ai/flux-2-trainer/api).
- **Retention.** Replicate: API prediction inputs/outputs/files/logs removed after about an hour by default; web predictions kept until deleted; trainings not covered on that page (**unverified** for training zips and the resulting LoRA). [Replicate data retention](https://replicate.com/docs/topics/predictions/data-retention). fal: request payloads kept 90 days by default (opt out per request with `X-Fal-Store-IO: 0`); CDN file lifetime configurable (default unclear); ZDR is not default. [fal data retention](https://fal.ai/docs/documentation/model-apis/media-expiration) (search summary, **secondhand**). fal privacy policy (updated 2026-07-22) says nothing explicit on training use of inputs. [fal privacy](https://fal.ai/privacy)
- **Workflow.** Train a LoRA (about $2-5, minutes), then generate with the trigger word and a prompt like a studio portrait. A LoRA is a file of your face you keep and must protect.

## 4. Zero-shot / reference-image identity (no training)

- **PuLID** (ByteDance, NeurIPS 2024; SDXL and FLUX variants; Apache-2.0). README does not state a reference count. PuLID-FLUX v0.9.0 "ID fidelity is not high enough for some male inputs"; v0.9.1 improved similarity about 5 points. FLUX version runs on 16 GB GPU (12 GB demo). No Mac/MPS mention. [GitHub](https://github.com/ToTheBeginning/PuLID)
- **InstantID** (SDXL). One reference image; only the largest face used. Code Apache-2.0 but insightface face models and checkpoints are non-commercial / research only. Example code is CUDA-oriented. [GitHub](https://github.com/instantX-research/InstantID)
- **PhotoMaker V2** (TencentARC, SDXL adapter). Accepts several photos of one person ("more photos improve ID fidelity"); 11 GB GPU minimum; README points Mac users to a separate setup note. Lower sampling steps and stylization reduce identity fidelity. [GitHub](https://github.com/TencentARC/PhotoMaker)
- **Gemini image models.** Nano Banana 2.1 / 3.1 Flash Image: up to 14 reference images total, up to 4 character images; Nano Banana Pro: up to 14 total, up to 5 character images. All outputs carry a SynthID watermark. Docs make no explicit likeness guarantee. [Gemini image docs](https://aistudio.google.com/docs/image-generation). Data: paid services are not used to improve Google products, prompts and responses logged for a limited period for abuse detection; unpaid services may be used for improvement with human review. [Gemini API terms](https://aistudio.google.com/docs/terms). A forum report says references keep faces consistent but ignore body scale (anecdotal, **secondhand**).
- **OpenAI image API.** Current docs list `gpt-image-2.5-*` and `2.6-*` models (the older `gpt-image-2` page is marked deprecated). Edits accept multiple input images (examples use up to 4; no maximum stated on the pages read). Guide says to name the face and proportions to keep fixed and to inspect outputs; omit `input_fidelity`. [Image generation](https://developers.openai.com/api/docs/guides/image-generation), [Image prompting](https://developers.openai.com/api/docs/guides/image-prompting). Data: API data not used for training by default; 30-day abuse-monitoring retention; image endpoints ZDR-eligible only with approval. [Your data](https://developers.openai.com/api/docs/guides/your-data)
- **FLUX.2 [klein] 4B** (Black Forest Labs). Apache 2.0, multi-reference editing, about 13 GB VRAM. Reference-count limit not stated on the model card. [Model card](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B)
- **Caveat across all of these.** Identity fidelity is vendor-claimed. I found no primary benchmark I could verify for "looks like you" quality. Expect drift in subtle features; check against real photos.

## 5. Running locally on Apple Silicon

- **mflux** (MLX, `uv tool install --upgrade mflux`): supports FLUX.1, FLUX.2, FLUX 3 Image Klein, Qwen Image 2.1, Z-Image and others. FLUX 3 Image Klein listed with editing from up to 10 reference images; Qwen Image 2.1 multi-reference editing; training marked supported for FLUX.2, Z-Image, Qwen Image 2.1 and some others, with LoKr on FLUX.1/FLUX.2. 8-bit quantization available. The README gave no RAM or speed numbers, so training cost on a Mac is **unverified**. [GitHub](https://github.com/filipstrand/mflux)
- **Draw Things.** Wiki: LoRA training for SD1.5, SDXL, FLUX.1, plus FLUX.2 [klein], Z-Image, Qwen Image; 8 GB RAM minimum, SDXL at 1024 typically needs 16-32 GB+, 16 GB Macs workable for FLUX inference with quantized weights, 36 GB+ ideal for training; typical 500-4000 steps. [Wiki](https://wiki.drawthings.ai/wiki/LoRa_Training_Notes), page edited 2026-08-23. **Open bug**: LoRA training writes zero-valued weights on M-series (reports May-Nov 2026 across M4/M5, FLUX.1 and SDXL), no maintainer response as of 2026-11-21. [Issue #81](https://github.com/drawthingsai/draw-things-community/issues/81). Wiki benchmark of about 9 s/step on M2 Ultra for FLUX.1 was seen in a search summary only (**secondhand**).
- **ComfyUI.** Uses PyTorch MPS on Apple Silicon; Comfy Desktop installs on macOS. MPS lacks FP8, so FP8 models often fail. [ComfyUI system requirements](https://docs.comfy.org/installation/system_requirements) (search summary, **secondhand**). Identity-adapter nodes on Mac: **unverified**.
- **ai-toolkit (Ostris).** Official macOS launcher marked experimental; issues report NaN losses/OOM for FLUX.2-dev on MPS, slow official path, and zero lora_B weights for a Krea2 run. [README](https://github.com/ostris/ai-toolkit), [issue #871](https://github.com/ostris/ai-toolkit/issues/871) (summaries, **secondhand**).
- **DiffusionKit.** Repository archived 2026-03-21; no LoRA or training. Skip. [GitHub](https://github.com/argmaxinc/DiffusionKit)
- **PuLID / InstantID / PhotoMaker on Mac.** None of the READMEs gives Apple Silicon instructions (PhotoMaker links a Mac note). Treat as untested.

Net: local inference and reference-image editing on a Mac look practical; local LoRA training on Mac looks unreliable right now.

## 6. Choosing input photos (as stated by the sources)

- Count: Replicate says 10 minimum (2 works), fast-flux-trainer 10-20, fal portrait 10+; HeadshotPro 2-3 selfies, Aragon a few to 6+; Gemini up to 4-5 character images.
- Variety: different settings, clothing, lighting, angles, expressions, backgrounds ([Replicate blog](https://replicate.com/blog/fine-tune-flux-with-faces), [fast-flux-trainer](https://replicate.com/replicate/fast-flux-trainer/readme), [Aragon](https://www.aragon.ai/blog/how-to-get-ai-headshot)).
- Resolution: 1024x1024 or higher (Replicate).
- Avoid: different haircuts or ages in one set; frequent hands near the face (Replicate); heavy filters, edits, obstructed or blurry shots, group shots, tiny faces, sunglasses (Aragon pages, **secondhand** for the last items); natural light and no harsh shadows (Aragon).

## 7. Comparison

| Path | Cost | Effort | Privacy | Likeness | Local? |
|---|---|---|---|---|---|
| Hosted service (HeadshotPro/Aragon) | $29-75 | Lowest | Vendor-stated 30-day deletion, no training; unauditable | Vendor-claimed; unverified | No |
| Hosted BetterPic | $35-79 | Lowest | Policy: inputs up to 1 yr, models up to 3 yrs | Vendor-claimed | No |
| LoRA via Replicate/fal | about $2-5 | Medium (zip, host, prompts) | Photos go to provider; training retention unclear | Generally strong with 10+ varied photos (docs claim; unverified) | No |
| Gemini / OpenAI reference editing | Per image, pennies (not verified) | Low-medium | Paid/API: no training; short abuse logs | Good but drifts; unverified | No |
| PuLID / InstantID / PhotoMaker | Free | High; CUDA-centric | Local if run locally | Documented fidelity gaps | Not on Mac without porting (unverified) |
| mflux with FLUX.2 klein / Qwen reference edit | Free | Medium-high | Nothing leaves the Mac | Unknown until tested | Yes |
| Local LoRA training (Draw Things, ai-toolkit) | Free | High | Best | Potentially best, but active bugs | Yes, unreliable |

## 8. Recommendation

- **Technical user who cares about privacy:** run mflux locally with a multi-reference edit model (FLUX.2 klein or Qwen Image 2.1; klein is Apache 2.0 and takes up to 10 references per mflux), feeding 4-10 varied, sharp photos and prompting for a plain-background shoulders-up portrait. Nothing leaves the machine. Test likeness against your real photos; if it is not good enough, fall back to a paid-tier Gemini or OpenAI API call (not trained on, short logs), and only then to Replicate/fal LoRA training. Do not rely on Draw Things training until issue #81 is fixed. Caveat: I did not run any of this, and mflux RAM and speed figures are unverified.
- **Least effort:** HeadshotPro (cheapest, quick, states 30-day deletion and no training) or Aragon (states 30-day face-data deletion). Upload the varied selfies they ask for, download your pick within the 30-day window, then delete your data in-account. Use a faithful pick, not the most flattering one.
- **Either way:** crop to LinkedIn's framing, export JPG/PNG under 8 MB at 400x400 or larger, and use an image that is recognizably you. That is the line LinkedIn's help text draws.

## Not verified

- Per-image cost of Gemini and OpenAI image calls (pricing pages not read).
- Replicate and fal retention of training zips and LoRA weights.
- BetterPic and Aragon current upload counts and BetterPic's marketing-vs-policy retention conflict.
- Any Mac memory and speed figures for mflux; ComfyUI and ai-toolkit status beyond search summaries.
- Likeness quality of any method (no primary benchmark checked).

## 9. Prompting research & reusable prompts

Checked 2026-11-23. Same sourcing rules as above. Fetch-tool extracts are model-written, so quotes below were taken from those extracts and are worth a glance at the source before you rely on exact wording. Many arXiv items are 2026 preprints I did not check for peer review.

### 9.1 First-party prompting guidance

**OpenAI** ([image prompting guide](https://developers.openai.com/api/docs/guides/image-prompting); [gpt-image-1.5 prompting guide](https://developers.openai.com/cookbook/examples/multimodal/image-gen-1.5-prompting_guide); [high input fidelity cookbook](https://developers.openai.com/cookbook/examples/generate_images_with_high_input_fidelity))
- Refer to inputs by number and role: "Identify each input by number and purpose: subject, style, clothing, or background." 1.5 guide: "Reference each input by index and description." (image-prompting guide; 1.5 guide section 2)
- Face wording from the guide's examples: "Do not change her face, facial features, skin tone, body shape, pose, or identity in any way." and "Preserve her exact likeness, expression, hairstyle, and proportions." For insertion, state "which facial features and proportions must remain unchanged." (image-prompting guide)
- Separate changes from constraints: "say 'change only X' and list the details to preserve, such as identity, geometry, layout, lighting, or labels." 1.5 guide: "'change only X' + 'keep everything else the same'".
- Iteration: "Pass the previous output as the next edit input, request one change, and repeat the details to preserve"; "Repeated edits can still change details you intended to preserve. Restate those constraints and inspect each result." "Keep each follow-up narrow."
- Realism (1.5 guide, section 4.3): "prompt the model as if a real photo is being captured in the moment"; "explicitly ask for real texture (pores, wrinkles, fabric wear, imperfections)"; "Avoid words that imply studio polish or staging"; camera terms (lens, aperture feel, lighting) steer realism more than generic quality words.
- Guide says omit `input_fidelity` on edits for current models. The older cookbook (gpt-image-1 era) says "only the first one you provide is preserved with extra richness in texture" and suggests compositing several faces into one image. That is for the old parameter and may not apply to gpt-image-2.x, which the guide says handles every image at high fidelity (**unverified for 2.5/2.6**; I could not read the last ~35k characters of the image-prompting page).

**Google, Gemini / Nano Banana** ([Google Cloud prompting guide](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana); [Gemini image docs](https://aistudio.google.com/docs/image-generation))
- Formula for references: "[Reference images] + [Relationship instruction] + [New scenario]"; "Be explicit about what to keep exactly the same"; "Iterate: Refine images with follow-up prompts in a conversational manner." The guide has no portrait or face-specific rules. The Gemini docs offer character-consistency slots (up to 4-5 character images) but my extract of the long docs page was truncated, so any face-specific advice there is **unread**.

**Black Forest Labs, FLUX.2** ([prompting guide](https://docs.bfl.ai/guides/prompting_guide_flux2))
- "When using multiple input images, clearly describe the role of each." Word order matters: "FLUX.2 pays more attention to what comes first"; order is subject, action, style, context. 30-80 words is "usually ideal". Character consistency means defining the character in detail and repeating the description every time. Camera cues like "Shot on Hasselblad X2D, 80mm lens, f/2.8, natural lighting". Pro API has a 9 MP input+output budget (about 8 refs at 1 MP). No dedicated portrait section.

### 9.2 Papers: what they say about references, strength and measurement

| Work | How identity is measured | Findings that affect you |
|---|---|---|
| [PhotoMaker (2312.04461)](https://arxiv.org/abs/2312.04461) | Face Sim from FaceNet embeddings (RetinaFace detect), plus DINO and CLIP-I; table: IP-Adapter 67.1, PhotoMaker 61.8, DreamBooth 49.8 | More input ID images improve fidelity, biggest jump from 1 to 2; CLIP-T (prompt following) declines linearly as images are added; weak at full-length portraits. Details read from the HTML version, not the abstract. |
| [InstantID (2401.07519)](https://arxiv.org/abs/2401.07519) | Uses antelopev2 face embeddings; no numeric metric in the text I read | States a trade-off between face fidelity and text control; boosting image-token strength "can inadvertently impair the editing abilities of text tokens". |
| [PuLID (2404.16022)](https://arxiv.org/abs/2404.16022) | Face Sim = cosine similarity of CurricularFace embeddings (an independent check model) | Higher ID fidelity disrupts the base model more; on SDXL a max-ID variant hit 0.773 Face Sim but lost prompt-following and image-element preservation. Not fully removed. |
| [IP-Adapter-FaceID (model card)](https://huggingface.co/h94/IP-Adapter-FaceID) | InsightFace `buffalo_l` ID embedding from the first detected face | Portrait variant takes multiple face images (example uses 5); card admits it does not reach perfect photorealism or ID consistency; research-only license. |
| [Arc2Face (2403.11641)](https://arxiv.org/abs/2403.11641) | Conditions on an ArcFace embedding directly | Search summary only (**secondhand**): ID-consistent generation from ArcFace vectors; code at [foivospar/Arc2Face](https://github.com/foivospar/Arc2Face) (MIT, 809 stars, last push 2025-10-10). Not read in full. |

2025-26 evaluations of frontier models (all arXiv preprints; search summaries plus page extracts, treat numbers as protocol-specific and not comparable across papers):
- [Localize, Don't Beautify (2608.02841)](https://arxiv.org/html/2608.02841): tested GPT Image 2.6 (Flare, Sunburst), Nano Banana 2.1, FLUX 3, Seedream 5.0 Pro via fal.ai at about $0.042-0.068 per image. The dominant failure was "generic beautification" (smoothed skin, whitened teeth, larger eyes) rather than refusal. Prompts used three fixed parts: an avoidance list, a "realism and identity anchor", and a scoped intensity limit ("change only facial tissue and contour; keep skin tone, color, exposure, and lighting identical to the input"). Prompt-only outputs did not keep the unchanged region unchanged (off-target change 3.14 vs 0.04 after client-side compositing). ArcFace median identity: Sunburst 0.761, Flare 0.777, Nano Banana 2.1 0.842; 0.6 used as a "heuristic reference threshold, not a clinically calibrated" cutoff; a high score can also mean the model changed nothing. Only 15 synthetic faces. Implication for you: add an explicit "no beautification, keep skin texture" clause, and score outputs; blending the model's face region back into your original is a technique, not needed for a fresh headshot.
- [Beyond Facial Consistency (2607.25622)](https://arxiv.org/html/2607.25622): ArcFace face score on its Pexels-100 benchmark, GPT-Image-2 0.8519 (highest of those compared), GPT-Image-1.5 about 0.33 in the search summary and Nano Banana 2 about 0.59 (**secondhand**). Single reference image per subject; no reference-count ablation.
- [Persistent Identity Preservation (2609.04151)](https://arxiv.org/abs/2609.04151): abstract-level only. Identity degrades with iterative edits, small subject scale, degraded inputs and multi-subject composition; good image quality does not guarantee identity. Metrics not read.
- [GEditBench v2 (2603.28547)](https://arxiv.org/html/2603.28547) and [PixelSmile (2603.25728)](https://arxiv.org/html/2603.25728): ArcFace-based; search summary says closed models struggle on small faces and GPT-Image shows moderate identity drift when expressions change. **Secondhand**, not opened.

What this means for prompting (my synthesis, marked as inference): use large, sharp, close face references; do not stack many sequential edits (go back to the originals each round); keep the look request narrow (wardrobe, background, light) so there is less room for drift; expect a trade-off between a bold style or expression request and likeness. I found no paper that tests prompt wording on gpt-image-2.x identity directly, so the exact phrasing is untested.

### 9.3 Open-source repos and prompt libraries

Metadata from the GitHub API, 2026-11-23. Most prompt repos are tiny, new and promotional; treat the prompts as starting points, not validated recipes.

| Repo | Stars | Last push | Licence | Notes |
|---|---|---|---|---|
| [Anil-matcha/Awesome-GPT-Image-2.5-API-Prompts](https://github.com/Anil-matcha/Awesome-GPT-Image-2.5-API-Prompts) | 3 | 2026-11-05 | CC BY 4.0 (per README) | Multi-reference headshot prompt |
| [yijzhu-netizen/awesome-ai-image-prompts](https://github.com/yijzhu-netizen/awesome-ai-image-prompts) | 0 | 2026-10-22 | CC BY 4.0, credit drawcue.com | Several headshot variants; promotes a site |
| [vicmini/awesome-image-to-image-prompts](https://github.com/vicmini/awesome-image-to-image-prompts) | 0 | 2026-11-23 | CC BY 4.0 (prompts) | 30 headshot prompts; README says "Sponsored by PictCraft" |
| [aivideoweb/awesome-gpt-image-2-5-prompts](https://github.com/aivideoweb/awesome-gpt-image-2-5-prompts) | 1 | 2026-09-22 | MIT | Structured "Constraints:" style |
| [Pixmind-io/awesome-gpt-image-2-prompts](https://github.com/Pixmind-io/awesome-gpt-image-2-prompts) | 14 | 2026-05-02 | MIT | Its LinkedIn headshot entry is text-to-image only (no identity clause) |
| [astriaai/headshots-starter](https://github.com/astriaai/headshots-starter) | 4458 | 2025-06-19 | MIT | A Next.js wrapper around Astria's paid fine-tune API (requires at least 4 images); prompts moved to Astria "packs", so no usable template in the repo. Skip. |
| [florestefano1975/comfyui-portrait-master](https://github.com/florestefano1975/comfyui-portrait-master) | 1251 | 2026-02-09 | GPL-3.0 | Portrait prompt builder node; no negative prompt found; not identity-preserving |
| [aigc-apps/sd-webui-EasyPhoto](https://github.com/aigc-apps/sd-webui-EasyPhoto) | 5132 | 2024-07-10 | Apache-2.0 | LoRA-based portrait pipeline; stale, SD WebUI, not read in detail |

Prompts, quoted verbatim:

- Anil-matcha (CC BY 4.0): "Using the attached photobooth strip as reference for the subject's face, generate a single professional LinkedIn-style headshot: neutral gray background, soft studio lighting, navy blazer, confident closed-mouth smile. Preserve the exact facial structure, skin tone, and hairstyle from the reference photos."
- yijzhu-netizen (CC BY 4.0, credit drawcue.com): "Using the uploaded photo as the face reference, keep the person's face, hairline, skin tone and features exactly the same. Professional corporate headshot, head and shoulders, wearing a tailored charcoal suit jacket over a plain white shirt, confident relaxed smile, looking straight at the camera. Seamless mid-grey studio backdrop, soft key light from the front-left with a gentle fill, subtle hair light, 85mm lens, f/4, sharp eyes, natural skin texture, square 1:1 crop."
- vicmini (CC BY 4.0): "Turn this selfie into a professional LinkedIn headshot: navy blazer over a white shirt, plain soft grey background, soft front light, head and shoulders, looking at the camera. Keep the face exactly the same."
- aivideoweb (MIT): "Asset: Natural professional portrait. Target aspect ratio: 4:5. Mode: edit. / Image 1 is a consenting adult portrait. Create a relaxed professional headshot near a large north-facing window, with a softly blurred warm-gray studio background and a plain charcoal crew-neck top. Frame from chest upward, eye-level, natural skin texture and a small unforced smile. / Constraints: Preserve identity, age, skin tone, facial proportions, hairstyle and distinctive marks; no beauty reshaping. / Render only explicitly requested image text. Do not add unrelated logos, signatures or captions."
- Pixmind (MIT), edit pattern note: "Use `input_fidelity: "high"` to preserve the subject's identity while changing the entire scene" (this is gpt-image-1 era; current guide says omit it). No published negative-prompt template exists in any repo I read; gpt-image models have no negative prompt field, so "avoid X" goes in the prompt text.
- Also found, not evaluated: [AdenXie/american-corporate-headshot](https://github.com/AdenXie/american-corporate-headshot) (0 stars, AGPL-3.0, pushed 2026-11-08, Chinese-language agent skill with preset styles and a visual QA step). Fetched README only.

### 9.4 Scoring likeness locally

| Tool | What | Apple Silicon | Licence / notes |
|---|---|---|---|
| [insightface](https://github.com/deepinsight/insightface) (30.3k stars, last push 2026-10-19) | ArcFace family; `buffalo_l` pack is the one the IP-Adapter card uses | Python package README lists automatic CoreML, CUDA, CPU provider selection (CoreML first), so it should run on a Mac; I did not run it | Code MIT, but pretrained models and the buffalo_l pack are non-commercial research, with a separate licensing contact; fine for personal scoring, not for a product |
| [deepface](https://github.com/serengil/deepface) (23.7k stars, last push 2026-11-20) | Wrapper with ArcFace, Facenet512, SFace and others; `DeepFace.verify(img1, img2, model_name="ArcFace")`, cosine default | README has no Mac notes (**unverified**); ONNX Runtime / TensorFlow / PyTorch backends | MIT wrapper; wrapped models carry their own licences |

Scoring notes:
- deepface's built-in ArcFace threshold is a cosine distance of 0.68 ([threshold.py](https://github.com/serengil/deepface/blob/master/deepface/config/threshold.py)), where distance = 1 minus similarity. Papers above report cosine similarity (a 0.6 heuristic cutoff in one paper). Do not mix the two scales.
- Compare each candidate to every one of your real photos and take the mean and minimum; rank the variants rather than trusting an absolute cutoff. Scores depend on face crop, pose and model, and a high score can mean the model barely changed anything. Also look at the image: ArcFace does not catch beautification or subtle age shifts (inference).
- Run scoring locally; there is no reason to upload your photos anywhere to do this.

### 9.5 Synthesized prompt template for gpt-image-2.5/2.6 multi-reference edits

Send 3-4 of your photos as the image inputs, best frontal one first (ordering rationale: older cookbook says first image gets extra detail; may not apply to 2.x, so keep the best frontal first anyway [C]). Notes in brackets map to sources below. Replace the angle brackets.

```
Images 1, 2, 3 and 4 are photos of the same real adult, me. Image 1 is the clearest front-facing reference; images 2-4 show other angles and lighting. [A]
Generate one new professional LinkedIn headshot of this person. [D]

Identity: keep the exact facial structure, face shape, eyes, nose, mouth, ears, eyebrows, skin tone, hairline, hairstyle, apparent age and distinctive marks (<freckles / moles / scars / glasses>) from the references. Do not beautify, slim, smooth, whiten teeth, enlarge eyes or change the expression's character. [B][E][F]

Scene (change only these): head-and-shoulders, chest up, eye-level, face filling about 60% of the frame, looking at the camera with a natural, closed-mouth or slight smile. Wearing <plain charcoal blazer over a white shirt>. Plain softly blurred <mid-grey> background. Soft window light from the front-left with gentle fill. Shot on an 85mm lens at f/4. [D][G][H][I]

Realism: real photograph, natural skin texture with visible pores and minor imperfections, natural flyaway hair; no retouching, no airbrushing, no studio-glamour polish, no stylized colour grade. [C][E]

Constraints: change only the clothing, background and lighting; keep everything about the face and hair exactly as in the references. No text, logos, watermark or extra people. Square 1:1 image. [B][F]
```

Iteration: if drift appears, resend the original references (not the previous output), change one thing per round, and paste the Identity and Constraints blocks again [A][B]. Generate several variants and rank with ArcFace plus your own eye (section 9.4).

Sources for each element:
- [A] Number and describe each input; one change per follow-up; restate preserve list: [OpenAI image prompting guide](https://developers.openai.com/api/docs/guides/image-prompting), [1.5 guide](https://developers.openai.com/cookbook/examples/multimodal/image-gen-1.5-prompting_guide). BFL says the same for roles of multiple inputs: [FLUX.2 guide](https://docs.bfl.ai/guides/prompting_guide_flux2).
- [B] "Change only X" plus preserve list, "Preserve her exact likeness, expression, hairstyle, and proportions": OpenAI guides above. Wardrobe-only edit pattern also in [aivideoweb](https://github.com/aivideoweb/awesome-gpt-image-2-5-prompts) ("Preserve identity, age, skin tone, facial proportions, hairstyle and distinctive marks; no beauty reshaping").
- [C] Real-photo framing, pores and imperfections, avoid studio polish: OpenAI 1.5 guide section 4.3. Ordering caveat on the first image: [OpenAI high-fidelity cookbook](https://developers.openai.com/cookbook/examples/generate_images_with_high_input_fidelity) (gpt-image-1 era).
- [D] Headshot scene wording (head and shoulders, 85mm, f/4, soft key plus fill, 1:1): [yijzhu-netizen](https://github.com/yijzhu-netizen/awesome-ai-image-prompts) (CC BY 4.0, credit drawcue.com), [Anil-matcha](https://github.com/Anil-matcha/Awesome-GPT-Image-2.5-API-Prompts) (CC BY 4.0). Using these prompts means crediting them per their licences.
- [E] No-beautification clause and an explicit avoidance list: [Localize, Don't Beautify](https://arxiv.org/html/2608.02841), where generic beautification was the dominant failure.
- [F] List named features to keep, including distinctive marks: OpenAI image-prompting guide ("state which facial features and proportions must remain unchanged").
- [G] Face about 60% of frame, shoulders to just above the head, simple background, smile: [LinkedIn Talent blog](https://www.linkedin.com/business/talent/blog/product-tips/tips-for-picking-the-right-linkedin-profile-picture).
- [H] Put the main subject first and keep it to roughly 30-80 words per block: [BFL FLUX.2 guide](https://docs.bfl.ai/guides/prompting_guide_flux2) (written for FLUX.2; applicability to OpenAI models is my assumption).
- [I] Camera and lighting terms steer realism more than generic quality words: OpenAI 1.5 guide section 2.

### 9.6 Could not verify in this section

- Whether the `input_fidelity` and "first image is richest" advice applies to gpt-image-2.5/2.6 (docs say omit the parameter; the last ~35k characters of the image-prompting page were not read).
- Any head-to-head test of prompt wording on gpt-image-2.x identity fidelity; none found. The template is a synthesis, not a validated recipe.
- Gemini docs' face or character-consistency specifics (page extract truncated); Arc2Face paper details; PhotoMaker/IP-Adapter ablation numbers beyond the text extracts; the GEditBench v2, PixelSmile and Persistent Identity papers' protocols (search or abstract level only).
- Whether insightface and deepface run well on Apple Silicon in practice (README claims only; nothing was installed or run), and whether insightface's model licence suits your use.
- Star counts and push dates are from the GitHub API on 2026-11-23, and several of the prompt repos are brand-new, so quality is unproven.

## 10. Iterating from a chosen candidate

Checked 2026-11-23. The feature: the human picks one output and asks for "more like that", with or without feedback such as "make my smile less smiley". It must keep likeness and must not drift over rounds. Sources: OpenAI guides downloaded as raw Markdown (`<page>.md`), so the OpenAI quotes below are **verbatim** ([image generation guide](https://developers.openai.com/api/docs/guides/image-generation), [image prompting guide](https://developers.openai.com/api/docs/guides/image-prompting)). The [openai-python SDK](https://github.com/openai/openai-python) type files were read on `main`; latest release v3.58.0, 2026-11-23. Paper findings come from fetch-tool extracts, which a model writes, so treat their numbers as approximate. Numbers read off figures are marked **(figure)**.

Note first: an earlier design rule rejected generated outputs as references, because feeding the best output back in "compounds drift". This design keeps that rule for the *identity* references. The chosen image goes in through a separate, labelled slot.

### 10.1 OpenAI-native options

**a) Images edit, with the chosen output as an extra input (what `generate.py` already calls).**
- `image` takes a list. The SDK says "You can provide up to 16 images" (`src/openai/types/image_edit_params.py`), so 3-4 refs plus the chosen image fit.
- Role wording, from the prompting guide: "Identify each input by number and purpose: subject, style, clothing, or background." Its two-image example: "Pass the scene photograph as image 1 and the dog photograph as image 2." Neither guide gives an ordering rule for plain multi-image edits. Only masks and markup are tied to the first image: "If you provide multiple input images, the mask will be applied to the first image" and "The markup overlay applies only to the first input image. Any additional images serve as references." So keep the real refs first, as now, and add the chosen image last.
- Suggested role sentence (my synthesis, untested), extending the existing `{image_roles}` sentence: "Images 1-4 are photos of the same real adult, me; they are the only source for my face and identity. Image 5 is an earlier generated headshot that I liked: copy its framing, pose, outfit, background and lighting, but do not copy its face; take every facial feature from images 1-4."
- `input_fidelity`: still omit it. The SDK says "For `gpt-image-2`, omit this parameter", and the 2.6 prompting guide says "Omit `input_fidelity` on image edits." The generation guide: "the API doesn't allow changing it because the model processes every image input at high fidelity automatically." That also means the chosen image is processed at full fidelity, face included. Nothing in the API makes the model pay less attention to the face in one input.

**b) Responses API `image_generation` tool, multi-turn.**
- Mechanics (generation guide, "Multi-turn image generation"): "either by providing image generation calls outputs within context (you can also just use the image ID), or by using the `previous_response_id` parameter." The image-ID form passes `{"type": "image_generation_call", "id": ...}` in the input; the JS example uses `"type": "item_reference"`.
- `action`: "keep `action: "auto"` to let the model decide, set `action: "generate"` to always create a new image, or set `action: "edit"` to force editing when an image is in context." Also: "If you force `edit` without providing an image in context, the call will return an error." The SDK `ImageGeneration` tool type confirms `action: Literal["generate", "edit", "auto"]`, default `auto` (`src/openai/types/responses/tool.py`). Its `model` list includes `gpt-image-2.6-sunburst` and `-flare` (the default is `gpt-image-2.6-sunburst`). Its `input_fidelity` docstring is the same as the Images API ("For `gpt-image-2`, omit this parameter").
- The tool type has no `n` field. I read its whole field list: action, background, complexity, frame_count, frame_duration_ms, input_fidelity, input_image_mask, model, moderation, output_compression, output_format, partial_images, quality, size, svg. So one tool call yields one image, and four variants mean four calls or a model choosing to call four times (inference from the type, not a documented statement).
- The mainline model rewrites the prompt: "the mainline model (for example, `gpt-5.5`) will automatically revise your prompt for improved performance." The rewrite is visible in `revised_prompt`. That rewrite can soften the carefully worded identity and constraint blocks, and the pipeline would have to diff it.
- Conversation state: with `previous_response_id`, earlier turns (including the original refs and every generated face) are carried in context. That is chaining by construction. Unless the client resends the originals, the latest image dominates (inference).

**c) Masks for local changes (the smile).**
- Images API `mask`: "An additional image whose fully transparent areas (e.g. where alpha is zero) indicate where `image` should be edited. If there are multiple images provided, the mask will be applied on the first image. Must be a valid PNG file, less than 4MB, and have the same dimensions as `image`." (SDK). Guide: "The image to edit and mask must be of the same format and size", and "The mask image must also contain an alpha channel."
- Precision: "Masking with GPT Image is entirely prompt-based. The model uses the mask as guidance, but may not follow its exact shape with complete precision." So a mouth mask does not guarantee that the eyes, nose and hair stay untouched.
- The OpenAI way to guarantee an unchanged region is client-side compositing: "If a region must remain pixel-identical, composite the approved edit into the original image instead of relying on prompting alone." This matches §9.2's Localize, Don't Beautify (off-target change 3.14 with prompt only vs 0.04 after compositing).
- For a smile edit, the chosen image must be image 1, with the refs after it. The mouth box can come from insightface's 5 keypoints (mouth corners), locally, without anyone viewing the image.
- Responses equivalent: `input_image_mask` (`file_id` or base64 `image_url`). `markup` (a transparent annotation PNG on image 1, "Cannot be combined with mask") is a second local-edit option. The SDK says it "Supports GPT Image 2.5", and the guide says markup works for "supported GPT-Image-2.5 and GPT-Image-2.6 models" on `/v1/images/edits`.

**d) Seed or variations.**
- None for gpt-image models. `seed` does not appear in `image_edit_params.py`, `image_generate_params.py` or the Responses `ImageGeneration` tool (grep of SDK `main`). The guides never mention a seed.
- The variations endpoint is dead. `image_create_variation_params.py`: "The legacy model used by the retired image variations endpoint. This endpoint no longer accepts requests." Its only models were `dall-e-2`/`dall-e-3` (retired 2026-05-12) and `gpt-image-1` (shut down 2026-10-23).
- So "more like that" can only be done as a new edit request: the same prompt plus an image of the pick, sampled `n` times. Exact re-rolls are impossible.

**e) Cost.**
- Rates: 2.6 image output "$30 per million billable tokens". For 2.5: "$8 per million image input tokens, $2 per million cached image input tokens, $30 per million image output tokens, $5 per million text input tokens". The 2.6 section points to the pricing page for its input rates. `generate.py` assumes the same $8/$30/$5.
- Images edit plus one extra input image: it adds one image's input tokens per request. `generate.py`'s own guess is 700-5,000 tokens per ref, so about $0.006-0.04 at $8/M. Outputs dominate (the project's high-quality guess of up to 9,000 tokens per image is about $0.27 each). So "more like this" costs about what a normal run with 5 inputs costs. I could not confirm whether input tokens are billed once per request or scale with `n` (**unverified**); `usage` from a real run will settle it. The estimator should count the chosen image as an extra ref.
- Mask edit: the same token rates. The guide says markup has "no extra fee" but says nothing explicit about masks.
- Responses: "Responses API requests include the mainline model's token usage in addition to image generation costs." There is one image per call, so `n` variants mean `n` calls, each billing its inputs again. A `previous_response_id` chain also carries every earlier turn's images as input (inference). The offset: "cached input pricing applies only to the image generation tool in the Responses API. It doesn't apply to direct Images API requests". And "their cached token counts aren't included in the Responses API output", so `cost_from_usage` could not verify the discount.

### 10.2 Identity drift: chaining versus restarting

- [Persistent Identity Preservation (2609.04151)](https://arxiv.org/html/2609.04151), now read beyond the abstract. ArcFace (insightface antelopev2) cosine to an identity anchor averaged over enrolment photos (§3.1.1).
  - Iterative editing (§4.3, Figs. 10-11): 4 chained edits, where drift "becomes part of the input to the next". gpt-image-2 fell from about 0.71 to 0.53 **(figure)**, nb2 from 0.65 to 0.5, and their own persistent-identity method from about 0.79 to 0.70. gpt-image-2.5-Sunburst was also tested; I did not get its numbers.
  - Quote: "preserving identity in a single edit does not necessarily translate into stable identity over a longer editing workflow."
  - On single edits: "identity drift is already visible for edits involving expression changes", and in-context models "often alter subtle facial characteristics", giving "a plausible yet perceptually different identity."
  - It does **not** test re-anchoring to the original photos against chaining, so "restart from the originals" is still my inference. The authors build a commercial competitor (Phota Labs) and the evaluation is not independent.
- [PixelSmile (2603.25728)](https://arxiv.org/html/2603.25728), expression editing. ID similarity averages ArcFace, AdaFace and FaceNet (§3.2).
  - Table 1: GPT-Image (version not stated in my extract) 0.5056 ID similarity vs Seedream 0.7221 and Nano Banana Pro 0.7107. GPT-Image had the highest expression accuracy. "GPT-Image generates more visible expression differences but introduces moderate identity drift" (§5.3).
  - General finding: "stronger editing often leads to identity degradation, while excessive identity constraints suppress effective expression transfer" (§5.4). Smile-only results for GPT-Image are not given.
- OpenAI says the same thing more softly: "Repeated edits can still change details you intended to preserve. Restate those constraints and inspect each result." Limitations: "the model may occasionally struggle to maintain visual consistency for recurring characters". Its own iteration advice ("Pass the previous output as the next edit input") chains outputs. That suits design edits, but the evidence above says it is the wrong default for a face.

Design implications (inference from the above):
1. Send the original refs on every round. A generated image never becomes an identity reference, and the chain depth for identity is always 0.
2. The chosen image is a scene reference only: framing, pose, outfit, background, light. Say so in the role sentence.
   - Stronger, untested option: blur or grey out the face box (insightface bbox) in a local copy of the chosen image before upload. Then the only face the model sees is the real one.
   - Cost of that option: what the human liked about the face in the pick, such as its exact expression, is not carried over and must be stated in words.
3. Never send the pick from a "more like this" round as the next round's chosen image without re-anchoring. Record `parent_run`, `chosen_sha256` and `depth` in run.json. Use the holdout score to stop drift, not trust.
4. Treat any expression request as the riskiest edit, and expect a lower score after it.

### 10.3 Turning free-text feedback into prompt changes

- OpenAI gives **no** worked example of changing an expression while keeping identity. I searched both guides' full Markdown for "expression", "smile" and "emotion". The only face wording locks the expression: "Do not change her face, facial features, skin tone, body shape, pose, or identity in any way. Preserve her exact likeness, expression, hairstyle, and proportions."
- Applicable rules:
  - "say 'change only X' and list the details to preserve" (§9.1)
  - "State which facial features and proportions must remain unchanged."
  - "Keep the person, pose, lighting, and composition unchanged so the edit stays local."
  - "request one change, and repeat the details to preserve"
  - "Keep each follow-up narrow so you can see which change helped."
- The conflict in `prompt.txt` is real. The Identity block says "Do not ... change the expression's character", and Constraints says "change only the clothing, background and lighting; keep everything about the face and hair exactly". An expression request contradicts both.
- Recommended handling (synthesis):
  - Route `{expression}` changes through a template variant that edits both lines. Identity: drop "or change the expression's character" and add "Keep the exact shape of the eyes, nose, lips, teeth, jaw and face; only the smile changes." Constraints: "change only the expression, clothing, background and lighting; keep the facial structure, skin, marks and hair exactly as in images 1-4."
  - Example scene clause for "less smiley": "looking at the camera with a softer, relaxed closed-mouth smile, lips together, cheeks relaxed, eyes unchanged."
  - This wording is not from OpenAI and is untested.
- Safety of the mapping (synthesis):
  - The agent maps feedback to one existing look field (`expression`, `outfit`, `background`, `lighting`) and shows the human the exact phrase before the spend gate. It never pastes raw feedback into the prompt. This matches the skill's "change one thing per round" and the dry-run validator.
  - Use the skill's existing expression options ("a calm, neutral expression", "a natural closed-mouth smile") as the first choices for smile feedback.
  - Refuse or push back on requests to change facial structure, age or skin ("slimmer face", "younger", "smoother skin"). They conflict with the Identity block, with the no-beautification clause (§9.2) and with LinkedIn's likeness rule (§1).
  - With no feedback, change no field and resample with the chosen image as scene reference.

### 10.4 Ranking "more like this" outputs

- Keep `holdout_median` as the primary score. It is the only one tied to the real person.
- Add `chosen_sim`, the cosine to the chosen image's embedding, as a second column. It shows whether a variant kept the look the human picked. It is not likeness: the chosen face is itself generated and may already have drifted.
- Add `delta_vs_chosen`, the variant's holdout median minus the chosen image's holdout median (rerun on the chosen file). A drop beyond the existing ~0.02 noise band is a drift warning.
- Add a "copied the generated face" flag that mirrors the existing copy rule: `chosen_sim - holdout_median > COPY_MARGIN` (0.10). The variant then sits closer to the pick than to the real person.
- Keep `max_ref_sim` and the copy flag computed against real refs only. Never add the chosen image to `refs`.
- Sort by holdout. Within the noise band, show `chosen_sim` so a no-feedback round can favour the variants nearest the pick. Every threshold here is a guess until calibrated on real runs.
- Prior art: Persistent Identity scores against an averaged anchor from several real photos, not the last output (§3.1.1). The holdout median already does the equivalent.

### 10.5 Recommendation and alternative

**Recommended: re-anchored resample (Images edit).**
- Call `images.edit` with the original refs as images 1..N (best frontal first) plus the chosen output as image N+1. The role sentence says N+1 is for framing, pose, outfit, background and lighting only, and every facial feature comes from 1..N.
- Change at most one look field from the feedback, using the expression-aware template variant in 10.3 when the field is `expression`. Use `n` = 2-4, the same spend gate, and the original refs reloaded from `photos/refs` as `--from` does today.
- Rank with holdout first, plus `chosen_sim`, `delta_vs_chosen` and the copied-generated-face flag. Record lineage in run.json, and accept the chosen image only through its own flag (for example `--like out/<ts>/NN.png`), never as a ref.
- Optional hardening: blur the face in the uploaded copy of the pick.
- Pros:
  - The identity anchor never moves, so repeated rounds cannot compound drift through the references.
  - Reuses the existing endpoint, cost estimator, sanitiser and tests.
  - `n` variants per call.
  - No mainline-model prompt rewriting.
- Cons:
  - The model still sees the generated face at full fidelity and may copy it. The flag catches this after the fact and blurring prevents it at a cost.
  - It is a fresh sample, so the result is "similar", never "the same picture with a smaller smile". The face can shift slightly in every variant.
  - It costs about one extra input image per run.

**Alternative: local mask edit of the pick, plus composite.**
- For narrow feedback (the smile), send the chosen image as image 1 with an alpha mask over the mouth area from insightface keypoints, then the refs as images 2..N. The prompt says "change only the mouth to a softer closed-mouth smile; keep everything else".
- Then composite only the masked region back into the chosen image locally, as OpenAI recommends for regions that must stay pixel-identical.
- Pros:
  - Everything the human liked stays pixel-identical outside the mouth.
  - Best for "same picture, one tweak".
- Cons:
  - Masks are "entirely prompt-based" and imprecise, and compositing can leave seams under different lighting.
  - The mouth is identity-bearing. PixelSmile and Persistent Identity both show expression edits cost identity, and edits stack if repeated on the result. Allow it once per pick, at depth 1 only.
  - It needs new mask and composite code and tests.
  - Rejected for this feature: the Responses multi-turn route. It chains generated images by design, has no `n`, adds mainline-model tokens, and rewrites the prompt. Its one advantage, cached-input pricing, cannot be verified from `usage`.

Not verified here: whether input-image tokens scale with `n`; 2.6 input-token rates (the 2.6 section only links the pricing page); whether the role sentence actually stops the model copying the chosen face; mask precision on faces; all thresholds above; the exact figure values in Persistent Identity. No API calls were made and no photos or outputs were opened.
