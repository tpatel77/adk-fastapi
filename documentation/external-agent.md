External Agent

What it does (layman)
Calls an external HTTP service, sending the current state as the request payload.
The response is saved back into state.

How to configure
- `type: external`
- `url`: Target URL (supports `{state_key}` placeholders).
- `method`: HTTP method (GET, POST, PUT, DELETE).
- `headers`: HTTP headers (supports `{state_key}` placeholders).
- `output_key`: Where to store the response text.

Variants and capabilities
- POST/PUT: sends state as JSON body.
- GET/DELETE: sends state as query params.
- Header templating for auth tokens stored in state.

Example
```yaml
- name: external_summarizer
  type: external
  url: "https://api.example.com/summarize"
  method: "POST"
  headers:
    Authorization: "Bearer {api_token}"
  output_key: external_summary
```
