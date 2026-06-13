# Assignment 1 Grower Web Map — Local Instructions

## Purpose

This folder owns the lightweight grower-level interactive web map subskill. It generates a single self-contained HTML file per grower using actual pipeline field boundaries, with no embedded rasters or heavy data bundles.

## Safe edit scope

Edits should stay in this folder and its children unless the user explicitly asks for a broader skill change. Do not change parent `SKILL.md`, sibling workflows, or root policy from this subskill task unless explicitly requested.

## Read nearby docs first

Read `GUIDE.md` first for usage instructions and CLI reference.

## Local validation

After generating a map, verify in a browser that:
1. All fields are visible
2. Sidebar lists all fields
3. Click-to-zoom works
4. Popup shows grower, farm, and field name
5. File size is under 500 KB

## Local-delta-only reminder

This nested AGENTS.md only records instructions that differ from the parent or root files. Do not duplicate root-wide asset, vendor, or validation policy here except this pointer to `../../../AGENTS.md`.
