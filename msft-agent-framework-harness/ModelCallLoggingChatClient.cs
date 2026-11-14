using Microsoft.Extensions.AI;

internal sealed class ModelCallLoggingChatClient(IChatClient innerClient, string modelService) : DelegatingChatClient(innerClient)
{
    private int _calls;

    public override async Task<ChatResponse> GetResponseAsync(
        IEnumerable<ChatMessage> messages,
        ChatOptions? options = null,
        CancellationToken cancellationToken = default)
    {
        Console.WriteLine($"Sending model request {Interlocked.Increment(ref _calls)} to {modelService}...");
        ChatResponse response = await base.GetResponseAsync(messages, options, cancellationToken);
        foreach (FunctionCallContent call in response.Messages.SelectMany(message => message.Contents).OfType<FunctionCallContent>())
        {
            Console.WriteLine($"Model proposed: {call.Name}");
        }

        return response;
    }
}
