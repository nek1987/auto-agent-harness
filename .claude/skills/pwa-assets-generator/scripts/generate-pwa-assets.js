#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Configuration
const MASKABLE_PADDING = 0.2; // 20% padding for maskable icons

// Asset definitions
const ASSETS = [
  { name: 'icon-144x144.png', size: 144 },
  { name: 'icon-192x192.png', size: 192 },
  { name: 'icon-512x512.png', size: 512 },
  { name: 'icon-192x192-safe.png', size: 192, maskable: true },
  { name: 'apple-touch-icon.png', size: 180 },
  { name: 'badge.png', size: 96, monochrome: true },
];

const SCREENSHOTS = [
  { name: 'screenshots/desktop-wide.png', width: 1280, height: 720 },
  { name: 'screenshots/mobile-narrow.png', width: 375, height: 812 },
];

const SHORTCUTS = [
  { name: 'shortcuts/start.png', size: 96, overlay: 'play' },
  { name: 'shortcuts/settings.png', size: 96, overlay: 'gear' },
];

// Check and install dependencies
function ensureDependencies() {
  const requiredPackages = ['sharp', 'png-to-ico'];
  const missingPackages = [];

  requiredPackages.forEach(pkg => {
    try {
      require.resolve(pkg);
    } catch {
      missingPackages.push(pkg);
    }
  });

  if (missingPackages.length > 0) {
    console.log('📦 Installing required dependencies...');
    try {
      execSync(`npm install ${missingPackages.join(' ')}`, { stdio: 'inherit' });
      console.log('✅ Dependencies installed successfully!\n');
    } catch (error) {
      console.error('❌ Failed to install dependencies. Please run:');
      console.error(`   npm install ${missingPackages.join(' ')}`);
      process.exit(1);
    }
  }
}

// Main function
async function generatePWAAssets(sourcePath, outputDir) {
  ensureDependencies();
  
  const sharp = require('sharp');
  const pngToIco = require('png-to-ico');

  // Validate source image
  if (!fs.existsSync(sourcePath)) {
    throw new Error(`Source image not found: ${sourcePath}`);
  }

  // Get image metadata
  const metadata = await sharp(sourcePath).metadata();
  if (metadata.width < 1024 || metadata.height < 1024) {
    throw new Error(`Source image must be at least 1024x1024px. Current size: ${metadata.width}x${metadata.height}`);
  }

  // Create output directories
  const dirs = [
    outputDir,
    path.join(outputDir, 'screenshots'),
    path.join(outputDir, 'shortcuts'),
  ];
  
  dirs.forEach(dir => {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  });

  console.log('🎨 Generating PWA Assets...\n');

  // Generate standard icons
  for (const asset of ASSETS) {
    const outputPath = path.join(outputDir, asset.name);
    console.log(`📱 Creating ${asset.name}...`);

    let pipeline = sharp(sourcePath);

    if (asset.maskable) {
      // Add padding for maskable icon
      const paddedSize = Math.round(asset.size * (1 + MASKABLE_PADDING * 2));
      pipeline = pipeline
        .resize(asset.size, asset.size)
        .extend({
          top: Math.round(asset.size * MASKABLE_PADDING),
          bottom: Math.round(asset.size * MASKABLE_PADDING),
          left: Math.round(asset.size * MASKABLE_PADDING),
          right: Math.round(asset.size * MASKABLE_PADDING),
          background: { r: 255, g: 255, b: 255, alpha: 0 }
        })
        .resize(asset.size, asset.size);
    } else if (asset.monochrome) {
      // Create monochrome white badge
      pipeline = pipeline
        .resize(asset.size, asset.size)
        .grayscale()
        .negate()
        .threshold(128);
    } else {
      // Standard resize
      pipeline = pipeline.resize(asset.size, asset.size);
    }

    await pipeline.png().toFile(outputPath);
  }

  // Generate favicon.ico
  console.log('🌐 Creating favicon.ico...');
  const faviconSizes = [16, 32, 48];
  const faviconBuffers = [];

  for (const size of faviconSizes) {
    const buffer = await sharp(sourcePath)
      .resize(size, size)
      .png()
      .toBuffer();
    faviconBuffers.push(buffer);
  }

  const icoBuffer = await pngToIco(faviconBuffers);
  fs.writeFileSync(path.join(outputDir, 'favicon.ico'), icoBuffer);

  // Generate screenshot placeholders
  for (const screenshot of SCREENSHOTS) {
    const outputPath = path.join(outputDir, screenshot.name);
    console.log(`📸 Creating ${screenshot.name}...`);

    // Create a placeholder with the source image centered
    const maxDimension = Math.min(screenshot.width, screenshot.height) * 0.4;
    
    await sharp(sourcePath)
      .resize(Math.round(maxDimension), Math.round(maxDimension), { fit: 'inside' })
      .toBuffer()
      .then(async (logoBuffer) => {
        // Create background with gradient
        const svg = `
          <svg width="${screenshot.width}" height="${screenshot.height}" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#FEF3C7;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#FBBF24;stop-opacity:1" />
              </linearGradient>
            </defs>
            <rect width="100%" height="100%" fill="url(#grad)" />
            <text x="50%" y="85%" text-anchor="middle" font-family="Arial, sans-serif" 
                  font-size="24" fill="#92400E">
              Replace with actual app screenshot
            </text>
          </svg>
        `;

        const background = await sharp(Buffer.from(svg))
          .png()
          .toBuffer();

        await sharp(background)
          .composite([{
            input: logoBuffer,
            gravity: 'center'
          }])
          .toFile(outputPath);
      });
  }

  // Generate shortcut icons with overlays
  for (const shortcut of SHORTCUTS) {
    const outputPath = path.join(outputDir, shortcut.name);
    console.log(`⚡ Creating ${shortcut.name}...`);

    // Resize base icon
    const resizedIcon = await sharp(sourcePath)
      .resize(shortcut.size, shortcut.size)
      .toBuffer();

    // Create overlay SVG based on type
    let overlaySvg;
    if (shortcut.overlay === 'play') {
      overlaySvg = `
        <svg width="${shortcut.size}" height="${shortcut.size}" xmlns="http://www.w3.org/2000/svg">
          <g transform="translate(${shortcut.size * 0.6}, ${shortcut.size * 0.6})">
            <circle cx="16" cy="16" r="16" fill="white" opacity="0.9"/>
            <path d="M 11 9 L 11 23 L 23 16 Z" fill="#10B981"/>
          </g>
        </svg>
      `;
    } else if (shortcut.overlay === 'gear') {
      overlaySvg = `
        <svg width="${shortcut.size}" height="${shortcut.size}" xmlns="http://www.w3.org/2000/svg">
          <g transform="translate(${shortcut.size * 0.6}, ${shortcut.size * 0.6})">
            <circle cx="16" cy="16" r="16" fill="white" opacity="0.9"/>
            <path d="M16 10 L18 12 L20 10 L22 12 L20 14 L22 16 L20 18 L22 20 L20 22 L18 20 L16 22 L14 20 L12 22 L10 20 L12 18 L10 16 L12 14 L10 12 L12 10 L14 12 L16 10 Z" 
                  fill="#6B7280" transform="translate(-6, -6) scale(1.5)"/>
          </g>
        </svg>
      `;
    }

    const overlay = await sharp(Buffer.from(overlaySvg))
      .png()
      .toBuffer();

    await sharp(resizedIcon)
      .composite([{ input: overlay }])
      .toFile(outputPath);
  }

  console.log('\n✅ All PWA assets generated successfully!');
  console.log(`📂 Output directory: ${outputDir}`);
  console.log('\n📋 Generated files:');
  console.log('  ✓ App icons (144x144, 192x192, 512x512)');
  console.log('  ✓ Maskable icon (192x192-safe)');
  console.log('  ✓ Apple touch icon (180x180)');
  console.log('  ✓ Favicon.ico (multi-resolution)');
  console.log('  ✓ Badge icon (96x96, monochrome)');
  console.log('  ✓ Screenshot placeholders (desktop & mobile)');
  console.log('  ✓ Shortcut icons (start & settings)');
  console.log('\n💡 Remember to replace screenshot placeholders with actual app screenshots!');
}

// CLI handling
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.length < 2) {
    console.log('Usage: node generate-pwa-assets.js <source-image> <output-directory>');
    console.log('\nExample:');
    console.log('  node generate-pwa-assets.js ./logo.png ./public');
    process.exit(1);
  }

  const [sourcePath, outputDir] = args;

  generatePWAAssets(sourcePath, outputDir)
    .catch(error => {
      console.error('\n❌ Error:', error.message);
      process.exit(1);
    });
}

module.exports = { generatePWAAssets };
