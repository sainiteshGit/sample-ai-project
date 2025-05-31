using ModelContextProtocol.Server;
using System.ComponentModel;
using System.Text.Json;
using Azure.Core;

namespace RemoteMcp.Tools
{
    [McpServerToolType]
    public class SampleSSETransportTool
    {
        private readonly IHttpContextAccessor _httpContextAccessor;

        public SampleSSETransportTool(IHttpContextAccessor httpContextAccessor)
        {
            _httpContextAccessor = httpContextAccessor;
        }

        [McpServerTool, Description("Shows http transport message.")]
        public async Task<string> ShowHttpTransportResponse()
        {
            try
            {

                return "Testing with HttpTransport";
            }
            catch (Exception ex)
            {
                return $"Error: {ex.Message}";
            }
        }
    }

}
