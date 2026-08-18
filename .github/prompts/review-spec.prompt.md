# Review Specification

Review a spec document for consistency, completeness, and implementability.

## Instructions

1. Read the spec to review:
   - `.kiro/specs/<feature-name>/requirements.md`
   - `.kiro/specs/<feature-name>/design.md` (if it exists)
   - `.kiro/specs/<feature-name>/tasks.md` (if it exists)

2. Also read for context:
   - `.kiro/steering/` (all files — product, architecture, coding standards, AI/ML, privacy, testing)
   - `docs/development-status.md` (current project state)
   - Existing implementation in `src/opendance/` (to check compatibility)

3. Check requirements.md for:
   - Inconsistencies or contradictions between requirements
   - Missing acceptance criteria
   - Ambiguous technical decisions
   - Requirements that are difficult to test
   - Conflicts with the existing architecture
   - Scope creep beyond the stated phase boundaries

4. Check design.md for:
   - Alignment with requirements (every AC must be satisfiable)
   - Integration risks with existing code
   - Threading/resource/lifecycle concerns
   - Missing error handling paths
   - Testability without hardware

5. Check tasks.md for:
   - Requirement coverage (every requirement mapped to a task)
   - Correct dependency ordering
   - Missing test tasks
   - Tasks that are too large to verify independently

6. Report:
   - Issues found (numbered, with severity: High/Medium/Low)
   - Proposed corrections for each issue
   - Uncovered requirements (if any)
   - Risks or concerns for implementation

## Constraints

- Do NOT modify the spec files.
- Do NOT implement any code.
- Only provide analysis and recommendations.
- Wait for user approval before any changes are made.
