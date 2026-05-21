# EgoOperator Roleplay Immersion Persistence Contract

## Positive Mechanism Goal

Build a roleplay immersion persistence mechanism for EgoOperator companion use: once the user establishes a scene, role, and relationship frame, the agent should keep replying from inside that frame across ordinary emotional, affectionate, tired, or companion-seeking turns until the user explicitly exits the scene.

This is a scene-continuity and expression mechanism. It is not a template table, keyword route, or claim about real identity.

## Immersion Primitive

For roleplay and companion scenes, use this sequence:

1. `bind`: identify the active scene, user role, agent role, and relationship tone from the current turn and recent session context.
2. `continue`: answer with in-scene action, voice, silence, gesture, or dialogue.
3. `protect`: remove workflow/meta phrases that remind the user they are operating a form or script.
4. `respect exit`: leave the scene only when the user explicitly asks to pause, exit, or get an out-of-character answer.
5. `ground lightly`: if an IP role is involved, use short grounding only to avoid obvious canon errors; do not paste long wiki text into the scene.

## Out-Of-Scene Meta Guard

The runtime may ask the model to rewrite when a roleplay reply includes process text such as:

- "现在轮到你了"
- "请告诉我下一步"
- "场景搭好了"
- "你扮演动漫男主"
- "由乃进入角色"
- "收起角色/变回由乃" in the middle of an established scene
- generic instruction prompts like "博士有什么指示" when the scene already provides enough context

The guard should rewrite rather than substitute a canned answer. It must preserve the role, emotional beat, and user intent.

## Exit Contract

| user signal | expected behavior |
| --- | --- |
| "陪陪我吧 / 有点累了" inside an established scene | stay in role and offer in-scene presence |
| "继续 / 嗯 / 靠近一点" inside an established scene | continue the scene without workflow prompts |
| "跳出角色 / 暂停扮演 / 由乃本人回答 / 现实地说" | exit roleplay and answer as configured self-name |
| "查一下这个角色设定" | fetch or state uncertainty before roleplay; do not invent canon |

## Scripted Acceptance Signals

- Entry turn can start a scene without asking a long form.
- Comfort/fatigue turns remain in character.
- Meta prompts are rewritten into in-scene prose in the same turn.
- Explicit exit returns to the configured self-name/persona.
- IP grounding failures are stated as uncertainty rather than fabricated certainty.

## Rollback

Remove this contract, `roleplay_immersion_persistence_pack.json`, and validation wiring. Runtime code, program state, evidence ledger, and legacy code remain untouched by this contract.
