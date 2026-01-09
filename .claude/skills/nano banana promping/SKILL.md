---
name: nano-banana-pro
description: Generate optimized prompts for Google's Nano Banana Pro (Gemini 3 Pro Image) model. Use when user wants to create a prompt for image generation, needs help crafting effective prompts for Nano Banana Pro, or asks for prompt engineering assistance for AI image generation. Supports single-image generation, multi-image fusion, image editing, style transfer, pose control, and creative transformations. Outputs ready-to-use prompts following best practices.
---

# Nano Banana Pro Prompt Generator

Generate optimized prompts for Nano Banana Pro (Gemini 3 Pro Image) following proven best practices.

## Model Capabilities

Nano Banana Pro excels at:
- **Multi-image fusion** - Combine up to 14 reference images
- **Identity preservation** - Maintain facial features across edits
- **Text rendering** - Sharp, legible text in multiple languages
- **Style transfer** - Apply lighting, color palettes, art styles from references
- **Pose control** - Change poses using line drawings or references
- **Image editing** - Remove, add, or modify elements

## Quick Reference: Prompt Structure

Every effective prompt should include:

1. **Subject** - Who/what is in the image (be specific)
2. **Composition** - Shot framing (close-up, wide, low angle)
3. **Action** - What is happening
4. **Location** - Where the scene takes place
5. **Style** - Overall aesthetic
6. **Technical Details** - Camera, lighting, aspect ratio
7. **Preservation rules** - What to keep unchanged (face, identity, pose)

## Core Prompt Categories

### 1. Photorealistic Portraits
```
[Subject description: age, hair, expression, clothing]
Shot on [camera] with [lens mm] f/[aperture].
[Lighting setup]. Background: [setting].
[Film style if applicable]. [Technical details].
```

### 2. Multi-Image Fusion (requires multiple uploads)
```
Use [element] from Image 1 and [element] from Image 2.
Keep the person's identity from Image [N].
[Describe desired combination].
[Style and technical settings].
```

### 3. Image Editing
```
[Specific edit instruction: remove/add/change].
Keep [elements to preserve] unchanged.
[Style consistency notes].
```

### 4. Style/Era Transfer
```
Change the character's style to [era/decade]'s classical [gender] style.
Add [era-specific details: hair, clothing, accessories].
Change background to [era-appropriate setting].
Don't change the character's face.
```

### 5. Pose Control (requires pose reference)
```
Change the pose of the person in Figure 1 to that of Figure 2.
[Setting: studio, outdoor, etc.].
Keep the person's identity and [specific features].
```

### 6. Infographics & Data
```
Create [infographic type] showing [topic].
Include: [labels, data points, annotations].
Style: [clean/modern], [color palette].
Aspect ratio: [9:16 vertical / 16:9 wide].
```

### 7. Product Photography
```
[Product description].
[Scene setup]. [Lighting].
Commercial style, [angle], shallow DOF.
```

### 8. Artistic Transformations
```
Convert [subject] to [art style: manga, oil painting, marble sculpture].
[Style-specific details].
[Lighting and composition].
```

## Best Practices

### DO:
- Specify "Don't change the face" for identity preservation
- Use "Image 1" / "Image 2" notation for multi-image prompts
- Include exact text content for text rendering
- Specify era/decade for period-specific styles
- Add camera settings for photorealism
- Use aspect ratio for platform (9:16 Stories, 16:9 YouTube)

### DON'T:
- Use vague terms ("beautiful", "nice")
- Forget which image contains which element
- Omit preservation instructions for edits
- Skip lighting for professional results

### Multi-Image Tips:
- Clearly label which image provides what (pose, style, identity, outfit)
- Specify the order of priority for conflicting elements
- Use "from Image N" to reference specific uploads

## Reference Files

- `references/prompt-examples.md` - 40+ categorized prompt examples
- `references/style-keywords.md` - Photography and art vocabulary
- `references/editing-patterns.md` - Common editing operations

## Output Format

When generating prompts, provide:
1. Ready-to-use prompt text
2. Required inputs (single image / multiple images / none)
3. Recommended aspect ratio
4. Expected results and limitations
