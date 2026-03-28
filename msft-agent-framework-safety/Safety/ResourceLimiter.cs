using System.Collections.Concurrent;

namespace AgentSafetySample.Safety;

/// <summary>
/// Implements rate limiting and resource constraints.
/// Prevents cost overruns, DoS, and context overflow.
/// </summary>
public sealed class ResourceLimiter
{
    private readonly int _maxRequestsPerMinute;
    private readonly int _maxOutputTokens;
    private readonly int _maxInputLength;
    private readonly ConcurrentDictionary<string, SlidingWindow> _windows = new();

    public ResourceLimiter(int maxRequestsPerMinute, int maxOutputTokens, int maxInputLength)
    {
        _maxRequestsPerMinute = maxRequestsPerMinute;
        _maxOutputTokens = maxOutputTokens;
        _maxInputLength = maxInputLength;
    }

    public int MaxOutputTokens => _maxOutputTokens;
    public int MaxInputLength => _maxInputLength;

    /// <summary>
    /// Checks if a request from a given user/session is within rate limits.
    /// </summary>
    public (bool Allowed, string? Error, int RemainingRequests) CheckRateLimit(string sessionId)
    {
        var window = _windows.GetOrAdd(sessionId, _ => new SlidingWindow(_maxRequestsPerMinute));
        var (allowed, remaining) = window.TryAcquire();

        if (!allowed)
        {
            return (false, $"Rate limit exceeded: max {_maxRequestsPerMinute} requests/minute. Try again in {window.TimeUntilNextSlot():F0} seconds.", 0);
        }

        return (true, null, remaining);
    }

    /// <summary>
    /// Validates input length against the configured maximum.
    /// </summary>
    public (bool Allowed, string? Error) CheckInputLength(string input)
    {
        if (input.Length > _maxInputLength)
        {
            return (false, $"Input too long: {input.Length} chars exceeds limit of {_maxInputLength}.");
        }
        return (true, null);
    }

    /// <summary>
    /// Gets usage statistics for a session.
    /// </summary>
    public (int RequestsInWindow, int MaxRequests) GetUsageStats(string sessionId)
    {
        if (_windows.TryGetValue(sessionId, out var window))
        {
            return (window.CurrentCount, _maxRequestsPerMinute);
        }
        return (0, _maxRequestsPerMinute);
    }

    private sealed class SlidingWindow
    {
        private readonly int _maxRequests;
        private readonly Queue<DateTimeOffset> _timestamps = new();
        private readonly object _lock = new();

        public SlidingWindow(int maxRequests)
        {
            _maxRequests = maxRequests;
        }

        public int CurrentCount
        {
            get
            {
                lock (_lock)
                {
                    PruneExpired();
                    return _timestamps.Count;
                }
            }
        }

        public (bool Allowed, int Remaining) TryAcquire()
        {
            lock (_lock)
            {
                PruneExpired();

                if (_timestamps.Count >= _maxRequests)
                {
                    return (false, 0);
                }

                _timestamps.Enqueue(DateTimeOffset.UtcNow);
                return (true, _maxRequests - _timestamps.Count);
            }
        }

        public double TimeUntilNextSlot()
        {
            lock (_lock)
            {
                if (_timestamps.Count == 0) return 0;
                var oldest = _timestamps.Peek();
                var elapsed = (DateTimeOffset.UtcNow - oldest).TotalSeconds;
                return Math.Max(0, 60 - elapsed);
            }
        }

        private void PruneExpired()
        {
            var cutoff = DateTimeOffset.UtcNow.AddMinutes(-1);
            while (_timestamps.Count > 0 && _timestamps.Peek() < cutoff)
            {
                _timestamps.Dequeue();
            }
        }
    }
}
