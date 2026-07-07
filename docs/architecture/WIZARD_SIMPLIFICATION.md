# Wizard Simplification

**Date:** 2026-07-06  
**Status:** Implemented  
**Related files:** `ui/tray/src/components/wizard/*`, `ui/tray/src/stores/wizard.ts`

## Summary

Simplified the first-launch onboarding wizard from a mandatory 4-step flow to a flexible 2-step quick setup with an optional advanced mode. Users can now choose between:

1. **Quick Setup** (recommended): Just pick folders and start using Cerebro
2. **Advanced Setup**: Full control over backend, models, and engine configuration

## Problem

The original wizard forced all users through 4 steps:
1. Choose backend (local/claude/offline)
2. Verify llama.cpp (if local)
3. Verify models (if local)
4. Configure folders

**Issues:**
- Most users don't need to configure backend manually (auto-detection works)
- The "choose backend" step confused new users
- Model verification could block progress
- Only the folders step was truly necessary

## Solution

### New Flow

```
Welcome Screen
├── Quick Setup → Folders → Done
└── Advanced Setup → Backend → (llama.cpp → Models) → Folders → Done
```

### Implementation Details

#### 1. New Component: `StepWelcome.tsx`

First screen of the wizard offering two options:
- **Quick Setup** (recommended): Skips backend/model configuration, uses defaults
- **Advanced Setup**: Shows the full original wizard flow

#### 2. Updated Store: `wizard.ts`

Added new state and methods:
```typescript
interface WizardState {
  currentStep: -1 | 0 | 1 | 2 | 3;  // -1 = welcome
  isQuickMode: boolean;               // true = quick setup
  setQuickMode: (quick: boolean) => void;
  // ... existing fields
}
```

Step flow:
- `-1` → Welcome screen
- `0` → Backend selection (advanced only)
- `1` → llama.cpp verification (advanced + local)
- `2` → Model verification (advanced + local)
- `3` → Folders (always required)

#### 3. Updated Shell: `WizardShell.tsx`

Dynamic step calculation based on mode:
- Quick mode: 2 steps (welcome → folders)
- Advanced mode: 2-5 steps depending on backend choice

#### 4. Translations

Added new keys to `locales/en.json` and `locales/es.json`:
- `wizard.step_welcome`
- `wizard.welcome_desc`
- `wizard.quick_setup`
- `wizard.recommended`
- `wizard.quick_setup_desc`
- `wizard.advanced_setup`
- `wizard.advanced_setup_desc`

## Benefits

1. **Faster onboarding**: New users can start in ~10 seconds
2. **Less confusion**: No need to understand backend/model concepts upfront
3. **Flexibility**: Power users can still access full configuration
4. **Backward compatible**: Advanced setup preserves all original functionality

## Testing

Updated `wizard.test.ts` to cover:
- Welcome step navigation
- Quick mode flow (welcome → folders → complete)
- Advanced mode flow (all steps)
- Reset behavior

## Future Improvements

- Auto-detect best backend based on RAM (already partially implemented)
- Show "You can change this later in Settings" hint
- Add "Don't show again" option for returning users
- Consider making folders optional with a default path

## Migration Notes

No backend changes required. The wizard state is stored client-side in Zustand and synced via `/api/wizard/complete` endpoint (unchanged).

Users who completed the old wizard will not see the new welcome screen (controlled by `is_first_launch` flag in backend).
