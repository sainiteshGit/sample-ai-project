# AI Gateway demo (Microsoft Foundry + Azure API Management)

A small console app that exercises the four things AI Gateway gives you:

| Scenario | What it shows | Policy you need on the APIM API |
|---|---|---|
| 1. Baseline | The SDK works unchanged when pointed at APIM. | none — just the auto-imported API |
| 2. Per-team metrics | Tokens attributed to `team=alpha` vs `team=beta`. | `<llm-emit-token-metric>` with a `Team` dimension |
| 3. Burst → 429 | Throttling kicks in once TPM is exhausted. | `<llm-token-limit tokens-per-minute="...">` |
| 4. Cache repeat | Second identical prompt is faster, 0 completion tokens. | `<llm-semantic-cache-lookup>` + `<llm-semantic-cache-store>` |

## Run

```bash
cp appsettings.Development.json.template appsettings.Development.json
# fill in your APIM gateway URL + subscription key + deployment name
dotnet run
```

## What you point it at

`Gateway:Endpoint` is your **APIM** URL (e.g. `https://my-apim.azure-api.net/openai`),
**not** your Foundry / Azure OpenAI endpoint. The whole point of the demo is to
show traffic going through the gateway.

`Gateway:ApiKey` is your APIM **subscription key**, not your Azure OpenAI key.

## Headers it sends

Every request gets:

- `x-team-id`: alpha / beta / burst-team / cache-test depending on scenario
- `x-app-id`: `ai-gateway-sample`
- `api-key`: your APIM subscription key (sent by the SDK)

Use those header names in your APIM policies, e.g.

```xml
<llm-emit-token-metric namespace="llm-metrics">
  <dimension name="Team" value="@(context.Request.Headers.GetValueOrDefault("x-team-id", "unknown"))" />
  <dimension name="App"  value="@(context.Request.Headers.GetValueOrDefault("x-app-id", "unknown"))" />
</llm-emit-token-metric>

<llm-token-limit
    counter-key="@(context.Request.Headers.GetValueOrDefault("x-team-id", "default"))"
    tokens-per-minute="500"
    estimate-prompt-tokens="true" />
```
