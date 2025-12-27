# Vendor Directory

This directory contains third-party binaries that are included in the Docker image.

## NAM VST3 Plugin

The Neural Amp Modeler VST3 plugin is required for audio processing.

### Download

Download from the official releases:
https://github.com/sdatkinson/NeuralAmpModelerPlugin/releases

1. Download `NeuralAmpModeler-linux-v0.7.13.zip` (or latest version)
2. Extract the `NeuralAmpModeler.vst3` folder
3. Place it in `vendor/vst3/NeuralAmpModeler.vst3/`

### Structure

```
vendor/
└── vst3/
    └── NeuralAmpModeler.vst3/
        └── Contents/
            └── ... (VST3 plugin files)
```

### Git LFS

Large binary files are tracked with Git LFS. If you clone the repo and the
VST files are missing, run:

```bash
git lfs pull
```
