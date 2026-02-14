# ORA-060: Source and integrate ambient sound assets

## Context
Meditation feature needs ambient background sounds for focus.

## Task
Find and integrate 6 royalty-free ambient sound loops.

## Sound Requirements
- **Format**: AAC or MP3
- **Size**: <2MB each
- **Length**: 30-60 second loops
- **Quality**: Seamless looping (no gaps/clicks)

## Sounds Needed
1. Rain
2. Ocean waves
3. Forest birds
4. White noise
5. Singing bowls
6. Stream/river

## Sources (royalty-free)
- Freesound.org
- Pixabay (audio)
- YouTube Audio Library
- Zapsplat

## Implementation
Files: /Users/matthew/Desktop/Feb26/ora-ai/

1. Download 6 sound files
2. Convert to AAC if needed (use ffmpeg)
3. Save to `assets/sounds/ambient/`:
   - rain.aac
   - ocean.aac
   - forest.aac
   - whitenoise.aac
   - bowls.aac
   - stream.aac

4. Update `MeditationScreen.tsx`:
   - Import Audio from expo-av
   - Add sound selector dropdown
   - Play selected sound on loop during meditation

## Testing
- Test each sound for seamless looping
- Verify file sizes <2MB
- Check playback quality

## Acceptance
- 6 high-quality ambient sounds integrated
- Sounds loop seamlessly
- Playable from meditation screen

## Project
- App: /Users/matthew/Desktop/Feb26/ora-ai/
