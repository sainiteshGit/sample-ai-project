using Microsoft.Agents.AI;

namespace MultiModelDebate;

/// <summary>
/// Orchestrates a multi-model debate where two agents backed by different models
/// independently answer, critique each other, and a judge synthesizes the best response.
///
/// Flow:
///   1. Parallel Generation — Both models answer the same question independently
///   2. Cross-Critique — Each model reviews the other's answer and provides feedback
///   3. Revision — Each model revises their answer based on the critique
///   4. Judgment — A judge agent picks or synthesizes the best final answer
/// </summary>
public sealed class DebateOrchestrator
{
    private readonly AIAgent _agentA;
    private readonly AIAgent _agentB;
    private readonly AIAgent _judge;
    private readonly int _maxRounds;
    private readonly string _modelAName;
    private readonly string _modelBName;

    public DebateOrchestrator(
        AIAgent agentA, string modelAName,
        AIAgent agentB, string modelBName,
        AIAgent judge, int maxRounds = 2)
    {
        _agentA = agentA;
        _modelAName = modelAName;
        _agentB = agentB;
        _modelBName = modelBName;
        _judge = judge;
        _maxRounds = maxRounds;
    }

    /// <summary>
    /// Runs the full debate pipeline: parallel answers → critique rounds → judgment.
    /// </summary>
    public async Task<DebateResult> RunDebateAsync(string question)
    {
        var result = new DebateResult { Question = question };

        // ── Step 1: Parallel Generation ──
        Console.WriteLine($"  ┌─ {_modelAName} answering...");
        var sessionA = await _agentA.CreateSessionAsync();
        var responseA = await _agentA.RunAsync(question, sessionA);
        result.InitialAnswerA = responseA.Text ?? "(no response)";
        Console.WriteLine($"  │  {Truncate(result.InitialAnswerA, 120)}");

        Console.WriteLine($"  ┌─ {_modelBName} answering...");
        var sessionB = await _agentB.CreateSessionAsync();
        var responseB = await _agentB.RunAsync(question, sessionB);
        result.InitialAnswerB = responseB.Text ?? "(no response)";
        Console.WriteLine($"  │  {Truncate(result.InitialAnswerB, 120)}");

        var currentAnswerA = result.InitialAnswerA;
        var currentAnswerB = result.InitialAnswerB;

        // ── Step 2 & 3: Critique Rounds ──
        for (int round = 1; round <= _maxRounds; round++)
        {
            Console.WriteLine($"\n  ── Debate Round {round}/{_maxRounds} ──");

            // A critiques B's answer
            var critiquePromptForA = $"""
                Another model was asked: "{question}"
                Their answer was: "{currentAnswerB}"
                
                Please critique this answer. Point out any errors, missing nuances, or improvements.
                Then provide your revised answer incorporating any valid points from the other model.
                
                Format:
                CRITIQUE: <your critique of their answer>
                REVISED ANSWER: <your improved answer>
                """;

            Console.WriteLine($"  ┌─ {_modelAName} critiquing {_modelBName}...");
            var critiqueResponseA = await _agentA.RunAsync(critiquePromptForA, sessionA);
            var critiqueA = critiqueResponseA.Text ?? "";
            Console.WriteLine($"  │  {Truncate(critiqueA, 120)}");

            // B critiques A's answer
            var critiquePromptForB = $"""
                Another model was asked: "{question}"
                Their answer was: "{currentAnswerA}"
                
                Please critique this answer. Point out any errors, missing nuances, or improvements.
                Then provide your revised answer incorporating any valid points from the other model.
                
                Format:
                CRITIQUE: <your critique of their answer>
                REVISED ANSWER: <your improved answer>
                """;

            Console.WriteLine($"  ┌─ {_modelBName} critiquing {_modelAName}...");
            var critiqueResponseB = await _agentB.RunAsync(critiquePromptForB, sessionB);
            var critiqueB = critiqueResponseB.Text ?? "";
            Console.WriteLine($"  │  {Truncate(critiqueB, 120)}");

            result.Rounds.Add(new DebateRound
            {
                RoundNumber = round,
                CritiqueByA = critiqueA,
                CritiqueByB = critiqueB,
            });

            // Extract revised answers for next round
            currentAnswerA = ExtractRevised(critiqueA) ?? critiqueA;
            currentAnswerB = ExtractRevised(critiqueB) ?? critiqueB;
        }

        result.FinalAnswerA = currentAnswerA;
        result.FinalAnswerB = currentAnswerB;

        // ── Step 4: Judgment ──
        Console.WriteLine($"\n  ── Judge ({_modelBName}) synthesizing final answer ──");
        var judgePrompt = $"""
            You are a judge evaluating two AI model responses to this question:
            "{question}"
            
            Model A ({_modelAName}) final answer:
            "{result.FinalAnswerA}"
            
            Model B ({_modelBName}) final answer:
            "{result.FinalAnswerB}"
            
            Evaluate both answers for accuracy, completeness, and clarity.
            Then provide a single best answer that combines the strongest elements from both.
            
            Format:
            EVALUATION: <brief comparison of both answers>
            BEST ANSWER: <your synthesized final answer>
            """;

        var judgeSession = await _judge.CreateSessionAsync();
        var judgeResponse = await _judge.RunAsync(judgePrompt, judgeSession);
        result.JudgmentText = judgeResponse.Text ?? "(no judgment)";
        result.FinalAnswer = ExtractBestAnswer(result.JudgmentText) ?? result.JudgmentText;

        Console.WriteLine($"  ✓ {Truncate(result.FinalAnswer, 150)}");

        return result;
    }

    /// <summary>
    /// Runs a simpler two-step pattern: parallel answers → direct judgment (no debate rounds).
    /// </summary>
    public async Task<DebateResult> RunConsensusAsync(string question)
    {
        var result = new DebateResult { Question = question };

        // Both models answer independently
        Console.WriteLine($"  ┌─ {_modelAName} answering...");
        var sessionA = await _agentA.CreateSessionAsync();
        var responseA = await _agentA.RunAsync(question, sessionA);
        result.InitialAnswerA = responseA.Text ?? "(no response)";
        Console.WriteLine($"  │  {Truncate(result.InitialAnswerA, 120)}");

        Console.WriteLine($"  ┌─ {_modelBName} answering...");
        var sessionB = await _agentB.CreateSessionAsync();
        var responseB = await _agentB.RunAsync(question, sessionB);
        result.InitialAnswerB = responseB.Text ?? "(no response)";
        Console.WriteLine($"  │  {Truncate(result.InitialAnswerB, 120)}");

        result.FinalAnswerA = result.InitialAnswerA;
        result.FinalAnswerB = result.InitialAnswerB;

        // Judge picks the best
        Console.WriteLine($"\n  ── Judge synthesizing ──");
        var judgePrompt = $"""
            Two AI models answered this question: "{question}"
            
            Model A ({_modelAName}): "{result.InitialAnswerA}"
            Model B ({_modelBName}): "{result.InitialAnswerB}"
            
            Pick the best answer or combine the strongest points from both into one clear response.
            Respond with only the final answer — no meta-commentary.
            """;

        var judgeSession = await _judge.CreateSessionAsync();
        var judgeResponse = await _judge.RunAsync(judgePrompt, judgeSession);
        result.JudgmentText = judgeResponse.Text ?? "(no judgment)";
        result.FinalAnswer = result.JudgmentText;

        Console.WriteLine($"  ✓ {Truncate(result.FinalAnswer, 150)}");
        return result;
    }

    private static string? ExtractRevised(string text)
    {
        var marker = "REVISED ANSWER:";
        var idx = text.IndexOf(marker, StringComparison.OrdinalIgnoreCase);
        if (idx >= 0)
            return text[(idx + marker.Length)..].Trim();
        return null;
    }

    private static string? ExtractBestAnswer(string text)
    {
        var marker = "BEST ANSWER:";
        var idx = text.IndexOf(marker, StringComparison.OrdinalIgnoreCase);
        if (idx >= 0)
            return text[(idx + marker.Length)..].Trim();
        return null;
    }

    private static string Truncate(string text, int max)
    {
        text = text.ReplaceLineEndings(" ");
        return text.Length <= max ? text : text[..max] + "...";
    }
}

public class DebateResult
{
    public string Question { get; set; } = "";
    public string InitialAnswerA { get; set; } = "";
    public string InitialAnswerB { get; set; } = "";
    public List<DebateRound> Rounds { get; set; } = [];
    public string FinalAnswerA { get; set; } = "";
    public string FinalAnswerB { get; set; } = "";
    public string JudgmentText { get; set; } = "";
    public string FinalAnswer { get; set; } = "";
}

public class DebateRound
{
    public int RoundNumber { get; set; }
    public string CritiqueByA { get; set; } = "";
    public string CritiqueByB { get; set; } = "";
}
