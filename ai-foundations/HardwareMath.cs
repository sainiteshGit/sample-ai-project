namespace Lab01;

/// <summary>
/// Experiments 8 and 9 need no API calls at all -- they are arithmetic.
///
/// This is deliberate. The most important fact in inference is a ratio you can
/// compute on paper, and once you have computed it yourself you will never
/// again be confused about why decode is slow, why batching exists, or why the
/// industry started fighting over memory instead of compute.
/// </summary>
internal sealed class HardwareMath(double measuredTpotMs)
{
    // ---- Reference hardware. Edit these to model a different GPU. ----
    private const double H100MemBandwidthGBs = 3350.0;   // HBM3, GB/s
    private const double H100PeakTFlopsBf16 = 989.0;     // dense, with sparsity off
    private const double A100MemBandwidthGBs = 2039.0;
    private const double A100PeakTFlopsBf16 = 312.0;

    // ---- Reference model: 70B parameters at FP16 (2 bytes each) ----
    private const double ParamsBillions = 70.0;
    private const double BytesPerParam = 2.0;

    // ======================================================================
    // 8. Why decode is memory-bound -- the roofline
    // ======================================================================
    public void Roofline()
    {
        Ui.Header(8, "Why decode is memory-bound (pure arithmetic, no API)");

        var modelBytes = ParamsBillions * 1e9 * BytesPerParam;
        var modelGb = modelBytes / 1e9;

        Console.WriteLine($"""

              Model:  {ParamsBillions:F0}B parameters at FP16 -> {modelGb:F0} GB of weights.

              ARITHMETIC INTENSITY (AI) = FLOPs performed / bytes moved from memory.
              It is the single number that decides whether you are compute-bound
              or memory-bound. Every GPU has a RIDGE POINT -- the AI at which it
              stops being starved for data and starts being limited by math.
            """);

        Console.WriteLine();
        Console.WriteLine($"  {"GPU",-8}{"bandwidth GB/s",18}{"peak TFLOP/s",15}{"ridge point",16}");
        Ui.Rule();
        Ridge("H100", H100MemBandwidthGBs, H100PeakTFlopsBf16);
        Ridge("A100", A100MemBandwidthGBs, A100PeakTFlopsBf16);
        Ui.Rule();

        Console.WriteLine($"""

              Now the two phases, for a {ParamsBillions:F0}B model.

              DECODE, batch size 1 -- generating ONE token:
                bytes moved  : {modelGb:F0} GB   (the ENTIRE model, every token)
                FLOPs        : ~2 x params = {2 * ParamsBillions:F0} GFLOP
                AI           = {2 * ParamsBillions * 1e9 / modelBytes:F1} FLOP/byte
            """);

        var decodeAi = 2 * ParamsBillions * 1e9 / modelBytes;
        var h100Ridge = H100PeakTFlopsBf16 * 1e12 / (H100MemBandwidthGBs * 1e9);
        var utilisation = decodeAi / h100Ridge * 100;

        Console.WriteLine($"""

              An H100 needs AI >= {h100Ridge:F0} to saturate its compute.
              Decode delivers AI = {decodeAi:F1}.

              You are running at roughly {utilisation:F2}% of the machine's compute
              capability. The GPU is almost entirely idle, waiting on memory.

              PREFILL, {1000} prompt tokens:
                bytes moved  : {modelGb:F0} GB   (the same weights, ONCE)
                FLOPs        : ~2 x params x tokens = {2 * ParamsBillions * 1000 / 1000:F0} TFLOP
                AI           = {2 * ParamsBillions * 1e9 * 1000 / modelBytes:F0} FLOP/byte
            """);

        var prefillAi = 2 * ParamsBillions * 1e9 * 1000 / modelBytes;
        Console.WriteLine($"""

              Prefill AI = {prefillAi:F0}, which is well past the ridge point of {h100Ridge:F0}.
              Prefill is COMPUTE-bound. Decode is MEMORY-bound. Same model, same
              GPU, same request -- opposite bottlenecks, minutes apart.

              THIS IS THE WHOLE STORY. Everything else in inference systems is a
              consequence of this one table.
            """);

        // ---- Predict token rate from bandwidth alone ----
        var predictedTokPerSec = H100MemBandwidthGBs * 1e9 / modelBytes;
        var predictedTpotMs = 1000.0 / predictedTokPerSec;

        Console.WriteLine();
        Ui.Rule('=');
        Console.WriteLine("  PREDICTION FROM PHYSICS ALONE");
        Ui.Rule('=');
        Console.WriteLine($"""

              If decode really is bandwidth-bound, then token rate should be
              almost exactly:

                  memory bandwidth / model size
                = {H100MemBandwidthGBs:F0} GB/s / {modelGb:F0} GB
                = {predictedTokPerSec:F1} tokens/sec       ({predictedTpotMs:F1} ms per token)

              on a single H100 at batch size 1.

              That is a prediction made with no benchmark, no profiler, and no
              knowledge of the model architecture beyond its parameter count.
              Published figures for 70B on a single H100 land in the 20-30 tok/s
              range. The prediction is close because the model is simple and the
              bottleneck is real.
            """);

        if (measuredTpotMs > 0)
        {
            // Invert the roofline: if decode is bandwidth-bound then
            //     TPOT = bytes_moved / bandwidth
            // so bytes_moved = TPOT x bandwidth. Bytes moved per token is
            // essentially the size of the weights, which gives a parameter
            // count for a model whose size nobody has published.
            var gbPerToken = H100MemBandwidthGBs * (measuredTpotMs / 1000.0);
            var paramsFp16 = gbPerToken / 2;
            var paramsFp8 = gbPerToken;

            Console.WriteLine($"""

              ======================================================================
              NOW RUN IT BACKWARDS ON A MODEL NOBODY HAS TOLD YOU THE SIZE OF
              ======================================================================

              Experiment 5 got a real per-token figure from the server's own
              clock: {measuredTpotMs:F1} ms/token.

              If decode is bandwidth-bound, then TPOT = bytes moved / bandwidth,
              so we can solve for the bytes:

                  bytes per token = {measuredTpotMs:F1} ms x 3350 GB/s = {gbPerToken:F0} GB

              That is roughly the weight footprint of the model serving you.
              Turn it into a parameter count:

                  if served at FP16 (2 bytes/param) -> ~{paramsFp16:F0}B parameters
                  if served at FP8  (1 byte/param)  -> ~{paramsFp8:F0}B parameters

              Treat that as an order of magnitude, not a measurement. It assumes
              H100-class bandwidth, ignores the KV cache reads, and -- most
              importantly -- your request was BATCHED with strangers'. Batching
              amortises the weight load across many sequences, which makes the
              real per-request byte cost lower than this and pushes the estimate
              UPWARD. So read it as a loose upper bound.

              But sit with what just happened. From one timing field, with no
              architecture details, no benchmark and no insider information, you
              bounded the size of a proprietary model to within an order of
              magnitude -- using nothing but a bandwidth number and division.

              That is what it means for a bottleneck to be REAL rather than
              incidental. When a system is pinned against physics, the physics
              tells you about the system.
            """);
        }

        Ui.Note("""
        WHY THIS MATTERS BEYOND TRIVIA

        Every headline in AI infrastructure follows from that ~0.3% number:

          * Why HBM sold out before GPUs did. If decode is bandwidth-bound, the
            scarce resource is memory bandwidth, not FLOPs. Vendors responded by
            shipping memory-only refreshes -- the H200 is an H100 with more and
            faster HBM and identical compute. That product exists because of
            this ratio.

          * Why quantisation is the highest-leverage optimisation. Halving the
            bytes per weight nearly halves decode latency, because you are
            moving half as much memory. It buys speed directly, not just space.

          * Why Mixture-of-Experts models exist. MoE activates only a fraction
            of parameters per token, so fewer bytes move. It is a bandwidth
            optimisation wearing an architecture costume.

          * Why everyone is suddenly interested in KV cache. Once weights are
            handled, the KV cache is the next thing competing for that same
            scarce bandwidth and capacity.
        """);

        static void Ridge(string name, double bwGbs, double tflops)
        {
            var ridge = tflops * 1e12 / (bwGbs * 1e9);
            Console.WriteLine($"  {name,-8}{bwGbs,18:F0}{tflops,15:F0}{ridge,13:F0} F/B");
        }
    }

    // ======================================================================
    // 9. Batching -- the escape hatch
    // ======================================================================
    public void Batching()
    {
        Ui.Header(9, "Batching: the escape hatch (pure arithmetic, no API)");

        var modelBytes = ParamsBillions * 1e9 * BytesPerParam;
        var h100Ridge = H100PeakTFlopsBf16 * 1e12 / (H100MemBandwidthGBs * 1e9);
        var tokPerSecTotal = H100MemBandwidthGBs * 1e9 / modelBytes;

        Console.WriteLine($"""

              The key insight: ONE load of the weights can serve MANY requests.

              The weights move from HBM to the compute units once per step,
              regardless of how many sequences are in the batch. So bytes stay
              constant while FLOPs multiply by batch size. Arithmetic intensity
              rises linearly with batch size -- for free.
            """);

        Console.WriteLine();
        Console.WriteLine($"  {"batch",8}{"AI (F/B)",12}{"% of ridge",13}{"tok/s total",14}{"tok/s each",13}");
        Ui.Rule();

        foreach (var b in new[] { 1, 4, 16, 64, 128, 256 })
        {
            var ai = 2.0 * ParamsBillions * 1e9 * b / modelBytes;
            var pctRidge = ai / h100Ridge * 100;
            var each = tokPerSecTotal;               // per-sequence rate stays ~flat
            var total = tokPerSecTotal * b;          // aggregate scales with batch
            var marker = ai >= h100Ridge ? "  <- compute-bound now" : "";
            Console.WriteLine($"  {b,8}{ai,12:F0}{pctRidge,12:F1}%{total,14:F0}{each,13:F1}{marker}");
        }

        Ui.Rule();

        Console.WriteLine($"""

              Read the last two columns carefully, because this is the trade that
              every inference platform is making on your behalf right now:

                tok/s TOTAL  goes up ~linearly with batch size.  (throughput)
                tok/s EACH   stays roughly flat.                 (your latency)

              So batching is nearly free throughput -- until AI crosses the ridge
              point at {h100Ridge:F0} F/B, after which you are genuinely compute-bound
              and further batching starts costing per-request latency.
            """);

        Ui.Note("""
        WHAT THIS EXPLAINS

        * WHY YOUR REQUEST IS BATCHED WITH STRANGERS' REQUESTS.
          At batch 1 a provider wastes 99.7% of the GPU. At batch 128 they are
          near the ridge. The economics are not close -- serving you alone would
          cost ~100x more. This is why every hosted API batches, and it is why
          you cannot get bit-exact reproducibility even at temperature 0:
          your batch neighbours change the floating-point reduction order.

        * WHY "CONTINUOUS BATCHING" WAS A BREAKTHROUGH.
          Naive static batching waits for every sequence in the batch to finish.
          One long generation stalls 127 short ones. Continuous batching evicts
          finished sequences and admits new ones every single step, keeping the
          batch full. It is work-stealing for token generation, and it roughly
          2-4x'd throughput industry-wide.

        * WHY KV CACHE MEMORY IS THE REAL LIMIT.
          Batching is free throughput, so why not batch 10,000? Because each
          sequence needs its own KV cache, and KV cache lives in the same HBM as
          the weights. Your maximum batch size -- and therefore the provider's
          entire cost structure -- is set by how much KV cache fits in memory.

          That is why PagedAttention mattered so much. By eliminating memory
          fragmentation it took KV utilisation from ~20-40% to >90%, which
          directly means a bigger batch, which directly means lower cost per
          token. A memory-management trick from 1960s operating systems is
          responsible for a large chunk of the price drop in LLM inference.

        * WHY PREFILL AND DECODE ARE BEING SPLIT ONTO DIFFERENT MACHINES.
          They have opposite bottlenecks (experiment 8), so co-locating them
          means one always interferes with the other. Prefill/decode
          disaggregation puts each phase on hardware suited to it. This is the
          current frontier of serving architecture.
        """);
    }
}
