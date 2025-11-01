# Fanout Fanin

```mermaid
flowchart TD
  dispatcher["dispatcher (Start)"];
  researcher["researcher"];
  marketer["marketer"];
  legal["legal"];
  aggregator["aggregator"];
  dispatcher --> researcher;
  dispatcher --> marketer;
  dispatcher --> legal;
  researcher --> aggregator;
  marketer --> aggregator;
  legal --> aggregator;
```
