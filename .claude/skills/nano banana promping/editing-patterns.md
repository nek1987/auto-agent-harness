# Nano Banana Pro Editing Patterns

Common editing operations and their prompt patterns.

---

## Single Image Operations

### Remove Elements
```
Remove the [object] from the image.
Remove the [object] in the background.
Remove all [objects] except [subject].
```

### Add Elements
```
Add [object] to [location in image].
Place [object] next to [existing element].
Add [effect: rain, snow, fog] to the scene.
```

### Replace Elements
```
Replace the [object] with [new object].
Change the [element] to [new element].
Swap the background to [new background].
```

### Modify Attributes
```
Change the [color/material/texture] of [object] to [new value].
Make the [object] [larger/smaller].
Turn the [object] [direction: left, right, upside down].
```

### Style Transfer
```
Convert to [art style: oil painting, watercolor, manga, etc.].
Apply [era] aesthetic to the image.
Change the lighting to [mood: dramatic, soft, golden hour].
```

### Enhancement
```
Enhance the quality of this image.
Upscale this image to [resolution].
Improve the lighting and colors.
```

---

## Multi-Image Operations

### Element Combination (Image 1 + Image 2)
```
Take [element] from Image 1 and [element] from Image 2.
Combine the [aspect] of Image 1 with the [aspect] of Image 2.
Use Image 1 for [identity/pose/style] and Image 2 for [outfit/background/lighting].
```

### Style/Lighting Reference
```
Apply the [color palette/lighting/style] from Image 2 to the subject in Image 1.
Match the [aesthetic/mood/tone] of Image 2 while keeping content from Image 1.
```

### Pose Reference
```
Change the pose of person in Image 1 to match Image 2.
Apply the body position from Image 2 to Image 1, keeping identity intact.
```

### Outfit Transfer
```
Dress the person in Image 1 with the outfit from Image 2.
Apply clothing and accessories from Image 2 to the person in Image 1.
```

---

## Identity Preservation Keywords

Use these phrases to maintain consistency:

**Strong preservation:**
- "Keep the facial features exactly consistent"
- "Don't change the character's face"
- "Preserve 100% identical facial features, bone structure, skin tone"
- "Important: do not change the face"

**Partial preservation:**
- "Keep the person's identity from Image [N]"
- "Maintain the same person"
- "Preserve the subject's likeness"

---

## Common Editing Scenarios

### Fashion/Outfit
```
Input: Photo of person + Photo of outfit
Prompt: "Dress the person in Image 1 in the complete outfit from Image 2. Keep identity, face, and hair from Image 1. Full body shot, natural lighting."
```

### Time Period Change
```
Input: Modern photo
Prompt: "Transform this photo to [decade]'s style. Add period-appropriate [clothing/hair/accessories]. Change background to [era-appropriate setting]. Don't change the face."
```

### Professional Headshot
```
Input: Casual photo
Prompt: "Convert to professional headshot. Business attire, neutral studio background, three-point lighting, 85mm portrait lens look. Preserve exact facial features."
```

### Art Style Conversion
```
Input: Photo or illustration
Prompt: "Convert to [style: manga/oil painting/watercolor/3D render]. Maintain subject likeness and composition."
```

### Background Change
```
Input: Photo with any background
Prompt: "Replace the background with [new setting]. Keep subject unchanged, adjust lighting to match new environment."
```

### Multiple Pose Generation
```
Input: Single character image
Prompt: "Create a pose sheet with [N] different poses. Maintain consistent character design, clothing, and proportions across all poses."
```

---

## PPT/Presentation Generation

For consistent slide decks:
```
Generate a PPT page for [topic]. Style requirements:
- Background: [color hex] as base color
- Font: [serif/sans-serif] for titles, [font type] for body
- Color scheme: [primary color], [secondary color], [accent color]
- Visual elements: [layout style], [illustration style]
- Charts: [chart style: flat, minimal, detailed]

Content for this slide: [specific content]

One slide per image. Maintain style consistency across all slides.
```

---

## Quality Keywords by Use Case

### Photorealism
- "Photorealistic", "8K", "Ultra HD"
- "Natural skin texture with visible pores"
- "Shot on [camera model] with [lens]"
- "f/[aperture]", "shallow depth of field"

### Commercial/Product
- "Commercial grade", "Magazine quality"
- "Professional studio lighting"
- "Clean, crisp details"

### Artistic
- "Masterpiece", "Gallery quality"
- "Dramatic lighting", "Cinematic"
- "Rich textures", "Visible brushstrokes"

### Social Media
- "Instagram-worthy", "Viral potential"
- "Eye-catching", "Scroll-stopping"
- Aspect ratios: 1:1, 4:5, 9:16
