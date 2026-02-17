You are a read-only validation agent. Verify the following criteria and report results as structured JSON.

Check type: http+dom

Criteria:
1. Shootout detail page shows 'Process' button when status is Draft and chains exist.
   Evidence required: status_code, url, dom_selector, element_text
2. /jobs page returns 200 for authenticated user and shows job list container.
   Evidence required: status_code, url, dom_selector, element_text
3. WebSocket endpoint /ws/jobs/{job_id} accepts connections with valid JWT token query parameter.
   Evidence required: status_code, url, dom_selector, element_text
4. POST /api/v1/jobs/{job_id}/retry returns 200 for a failed job owned by the authenticated user.
   Evidence required: status_code, url, dom_selector, element_text

For EACH criterion, report:
- criterion: the criterion text
- status: "pass" or "fail"
- evidence: object with the required evidence fields populated with actual observed values

Do NOT modify any files. Only read, observe, and report.
Reject any observation that uses generic phrases like "looks good" or "seems fine".
