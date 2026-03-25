export default async (
  context: PlatformContext,
  data: BeforeDownloadRequestRequest
): Promise<BeforeDownloadRequestResponse> => {
  const artifactId = data.metadata.originalRepoPath?.id ?? data.metadata.originalRepoPath?.path ?? "unknown";
  const repo = data.metadata.repoPath.key;
  const path = data.metadata.originalRepoPath.path;

  let status: ActionStatus = ActionStatus.UNSPECIFIED;
  let message: string;

  try {
    console.log(data);
    const res = await context.clients.platformHttp.get(
      `/artifactory/api/storage/${repo}/${path}?properties`
    );
    console.log(res);
    const properties = res?.data?.properties ?? {};
    const propertiesStr = JSON.stringify(properties);

    const isApproved = isApprovedFromResponse(res.data);
    if (isApproved) {
      status = ActionStatus.PROCEED;
      message = `Artifact approved. Proceeding. [artifact: ${artifactId}] [properties: ${propertiesStr}]`;
    } else {
      status = ActionStatus.STOP;
      message = `Artifact not approved or 'approved' property missing. [artifact: ${artifactId}] [properties: ${propertiesStr}]`;
    }
  } catch (error) {
    status = ActionStatus.STOP;
    message = `Request failed for artifact [${artifactId}]. ${error.message ?? String(error)}`;
    console.error(
      `Request failed with status code ${error.status ?? "<none>"} caused by: ${error.message}`
    );
  }

  console.log(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>");
  console.log(status);
  console.log(message);
  console.log(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>");
  return {
    status,
    message,
    modifiedRepoPath: data.metadata.repoPath,
  };
};

function isApprovedFromResponse(
  data: { properties?: { approved?: unknown } } | null | undefined
): boolean {
  const approved = data?.properties?.approved;
  return Array.isArray(approved) && approved[0] === "true";
}