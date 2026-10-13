# AI.md — AI Assistance & Verification Disclosure

## 1. AI Tool Usage Disclosure

In compliance with the assignment specification, this document transparently describes the AI tools and assistants used during the development of the **Bruviti AI Campus Hiring — Software License Usage & Cost Analytics** project.

- **Primary Assistant**: Google Gemini / Antigravity AI Pair Programming Assistant.
- **Role**: Software engineering pair programmer and testing assistant.

---

## 2. Contributions by the AI Assistant

The AI assistant assisted across the development lifecycle:
1. **Requirements Deconstruction**:
   - Analyzed the assignment brief, cross-checking all business rules, edge cases, proration formulas, and hierarchical traversal requirements.
2. **Architecture & Project Scaffolding**:
   - Proposed a decoupled project structure separating data loading, rule-based cleaning, organization traversal, metrics calculations, and API routing.
3. **Data Cleaning & Boundary Calculations**:
   - Formulated the exact boundary arithmetic for seat revocation (`seat_end = revoked_on - 1 day`) where `revoked_on` is explicitly the first day *without* the seat.
   - Designed the cycle-safe BFS traversal for organization trees with visited sets.
4. **Comprehensive Test Suite Formulation**:
   - Drafted the 28 required test cases spanning date boundaries, prorated spend, zero-division avoidance, unpriced tools, and malformed CSV recovery.
5. **Frontend Dashboard Design**:
   - Authored the vanilla HTML5/CSS3/JavaScript single-page dashboard with KPI cards, dynamic table rendering, client-side validation, error banners, and loading spinners.

---

## 3. Human Verification & Engineering Validation

All code, logic, and tests generated with AI assistance were strictly verified:
1. **Boundary & Math Verification**:
   - Manually walked through the intersection math for boundary edge cases (seat granted on first day, revoked on first day, revoked on last day, open-ended seats) against analytical hand-calculated examples.
2. **Formula Integrity**:
   - Verified that `seat_spend = (monthly_price / 30.0) * eligible_days` uses floating-point precision during intermediate summation, and that only final outputs are rounded.
3. **Defensive Coding Review**:
   - Inspected hierarchy traversal for cycle handling, self-referencing nodes, and missing parent nodes to ensure infinite loops and crashes are impossible.
4. **Security & Input Sanitization**:
   - Ensured date inputs are strictly parsed using standard formats (`YYYY-MM-DD`), paths are constrained within the project directory, and no raw stack traces or internal paths are exposed to API callers.
5. **No Hallucinated Data**:
   - Verified that no fictitious data was passed off as official assignment data; synthetic fixtures were explicitly labeled in `data/` and documented in `DATA.md`.
