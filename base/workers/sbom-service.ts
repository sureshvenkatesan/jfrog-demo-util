// @ts-nocheck
type CustomPayload = void;

interface CustomResponse {
  message: string | undefined;
  sbom?: string;
}

interface ImpactedArtifact {
  name: string;
  display_name: string;
  path: string;
  pkg_type: string;
  sha256: string;
  sha1: string;
  depth: number;
  parent_sha: string;
  infected_files: any[];
  vulnerable_components: any[];
}

interface Issue {
  vulnerability_id: string;
  severity: string;
  type: string;
  provider: string;
  created: string;
  summary: string;
  description: string;
  impacted_artifacts: ImpactedArtifact[];
  cve?: string;
  cwe?: string[];
  cvss_v2?: string;
  cvss_v3?: string;
  references?: any;
}

interface XrayWebhookPayload {
  schema_version: string;
  alert_id: string;
  created: string;
  top_severity: string;
  watch_name: string;
  policy_name: string;
  policy_rule: string;
  issues: Issue[];
}

interface PlatformContext {
  platformUrl?: string;
  getPlatformUrl?: () => string;
  platformToken?: string;
  authToken?: string;
  getAuthToken?: () => string;
  token?: string;
  clients?: {
    platformHttp?: any; // PlatformHttpClient - generic HTTP client to communicate with the platform
    axios?: any; // AxiosInstance - generic HTTP client to communicate with external web resources
    http?: {
      request: (options: {
        method: string;
        url: string;
        headers: Record<string, string>;
        body: string;
      }) => Promise<any>;
    };
    [key: string]: any;
  };
  http?: {
    request: (options: {
      method: string;
      url: string;
      headers: Record<string, string>;
      body: string;
    }) => Promise<any>;
  };
  request?: (options: {
    method: string;
    url: string;
    headers: Record<string, string>;
    body: string;
  }) => Promise<any>;
  wait?: (ms: number) => Promise<void>;
  secrets?: Record<string, any>;
  [key: string]: any;
}



function createCycloneDXFromXrayPayload(payload: XrayWebhookPayload): any {
  // Collect all unique components from all issues
  const componentsMap = new Map<string, any>();
  const vulnerabilities: any[] = [];

  for (const issue of payload.issues || []) {
    // Process each impacted artifact as a component
    for (const artifact of issue.impacted_artifacts || []) {
      const componentKey = `${artifact.pkg_type}:${artifact.display_name}`;
      
      if (!componentsMap.has(componentKey)) {
        // Extract version from display_name (e.g., "PyYAML:5.2" -> "5.2")
        const versionMatch = artifact.display_name.match(/:([^:]+)$/);
        const version = versionMatch ? versionMatch[1] : undefined;
        const name = artifact.display_name.split(':')[0];

        // Map package type to CycloneDX purl type
        const pkgTypeMap: Record<string, string> = {
          'pypi': 'pypi',
          'npm': 'npm',
          'maven': 'maven',
          'docker': 'docker',
          'nuget': 'nuget',
          'golang': 'golang',
          'composer': 'composer',
          'rpm': 'rpm',
          'deb': 'deb',
          'gem': 'gem',
          'generic': 'generic'
        };
        const normalizedPkgType = artifact.pkg_type.toLowerCase();
        const purlType = pkgTypeMap[normalizedPkgType] || 'generic';

        const component: any = {
          'bom-ref': `pkg:${purlType}/${name}${version ? '@' + version : ''}`, // Unique identifier for this component
          type: 'application', // Match exported format
          name: name,
          version: version,
          purl: `pkg:${purlType}/${name}${version ? '@' + version : ''}`,
          hashes: []
        };

        // Add hashes - only SHA-256 to match exported format
        if (artifact.sha256) {
          component.hashes.push({
            alg: 'SHA-256',
            content: artifact.sha256
          });
        }

        componentsMap.set(componentKey, component);
      }
    }

    // Create vulnerability entry
    const vulnerability: any = {
      id: issue.cve || issue.vulnerability_id || `XRAY-${issue.vulnerability_id}`,
      ratings: [],
      description: issue.description || issue.summary || ''
    };

    // Add CVSS ratings - match exported format (no source objects, CVSSv31 instead of CVSSv3)
    if (issue.cvss_v2) {
      const cvss2Match = issue.cvss_v2.match(/([\d.]+)/CVSS:2\.0/(.+)/);
      if (cvss2Match) {
        vulnerability.ratings.push({
          score: parseFloat(cvss2Match[1]),
          severity: issue.severity?.toLowerCase() || 'unknown',
          method: 'CVSSv2',
          vector: cvss2Match[2]
        });
      }
    }

    if (issue.cvss_v3) {
      const cvss3Match = issue.cvss_v3.match(/([\d.]+)/CVSS:3\.\d/(.+)/);
      if (cvss3Match) {
        vulnerability.ratings.push({
          score: parseFloat(cvss3Match[1]),
          severity: issue.severity?.toLowerCase() || 'unknown',
          method: 'CVSSv31', // Match exported format
          vector: cvss3Match[2]
        });
      }
    }

    // If no CVSS, use severity
    if (vulnerability.ratings.length === 0) {
      vulnerability.ratings.push({
        severity: issue.severity?.toLowerCase() || 'unknown'
      });
    }

    // Add CWE if present - convert strings like "CWE-20" to numbers like 20
    if (issue.cwe && issue.cwe.length > 0) {
      vulnerability.cwes = issue.cwe.map((cwe: string) => {
        // Extract number from "CWE-20" -> 20
        const match = cwe.match(/CWE-(\d+)/);
        return match ? parseInt(match[1], 10) : cwe;
      });
    }

    // Add affected components - use purl as ref
    vulnerability.affects = [];
    for (const artifact of issue.impacted_artifacts || []) {
      const componentKey = `${artifact.pkg_type}:${artifact.display_name}`;
      const component = componentsMap.get(componentKey);
      if (component) {
        vulnerability.affects.push({
          ref: component['bom-ref'] || component.purl || componentKey
        });
      }
    }

    vulnerabilities.push(vulnerability);
  }

  // Build CycloneDX BOM - match exported format
  // Generate UUID-like serialNumber
  const generateUUID = (): string => {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  };
  
  const components = Array.from(componentsMap.values());
  const firstComponent = components.length > 0 ? components[0] : null;
  
  const cyclonedx: any = {
    $schema: 'http://cyclonedx.org/schema/bom-1.6.schema.json',
    bomFormat: 'CycloneDX',
    specVersion: '1.6',
    serialNumber: `urn:uuid:${generateUUID()}`,
    version: 1,
    metadata: {
      timestamp: payload.created || new Date().toISOString(),
      tools: [{
        vendor: 'JFrog Inc.',
        name: 'Xray',
        version: '1.0' // Could be updated if version is available in payload
      }]
    },
    components: components
  };

  // Add root component to metadata if we have components (match exported format)
  if (firstComponent) {
    cyclonedx.metadata.component = {
      type: 'application',
      name: firstComponent.name,
      version: firstComponent.version,
      purl: firstComponent.purl
    };
  }

  // Add dependencies array (empty, matching exported format)
  cyclonedx.dependencies = [];

  // Add vulnerabilities if present
  if (vulnerabilities.length > 0) {
    cyclonedx.vulnerabilities = vulnerabilities;
  }

  return cyclonedx;
}

export default async (
  context: PlatformContext,
  data: CustomPayload
): Promise<CustomResponse> => {
  const response: CustomResponse = {
  message: undefined,
  sbom: undefined
  };

  try {

  const payload = data as unknown as XrayWebhookPayload;
  console.log('[INFO] Worker execution started');
  console.log(`[INFO] Payload alert_id: ${payload.alert_id || 'unknown'}`);
  console.log(`[INFO] Payload created: ${payload.created || 'unknown'}`);
  console.log(`[INFO] Payload watch_name: ${payload.watch_name || 'unknown'}`);
  console.log(`[INFO] Processing ${payload.issues?.length || 0} issue(s) from watch: ${payload.watch_name}`);

  // Log payload structure for debugging
  console.log(`[INFO] Payload structure: ${JSON.stringify({
    alert_id: payload.alert_id,
    created: payload.created,
    watch_name: payload.watch_name,
    issues_count: payload.issues?.length || 0,
    top_severity: payload.top_severity
  })}`);

  if (!payload.issues || payload.issues.length === 0) {
    console.warn('[WARN] No issues found in webhook payload');
    response.message = 'No issues found in webhook payload';
    return response;
  }

  const artifacts = new Map<string, ImpactedArtifact>();
  
  for (const issue of payload.issues) {
    if (issue.impacted_artifacts) {
    for (const artifact of issue.impacted_artifacts) {

      const key = `${artifact.pkg_type}:${artifact.display_name}`;
      if (!artifacts.has(key)) {
      artifacts.set(key, artifact);
      }
    }
    }
  }

  console.log(`[INFO] Found ${artifacts.size} unique artifact(s) to process`);
  if (artifacts.size === 0) {
    console.warn(`[WARN] No artifacts found in payload. Issues count: ${payload.issues?.length || 0}`);
  }

  // Check if any impacted artifact name is a .json file - exit early if so
  for (const issue of payload.issues || []) {
    for (const artifact of issue.impacted_artifacts || []) {
      const artifactName = artifact.name || artifact.display_name || '';
      if (artifactName.toLowerCase().endsWith('.json')) {
        console.log(`[INFO] Exiting worker: impacted artifact name "${artifactName}" is a .json file`);
        response.message = `Skipped processing: impacted artifact "${artifactName}" is a .json file`;
        return response;
      }
    }
  }

  const authToken = (context as any)?.platformToken || 
           (context as any)?.authToken || 
           (context as any)?.getAuthToken?.() || 
           (context as any)?.token || 
           '';
  

  // Generate CycloneDX JSON from webhook payload
  console.log(`[INFO] Generating CycloneDX JSON from webhook payload...`);
  console.log(`[INFO] Payload data being used: alert_id=${payload.alert_id}, created=${payload.created}, issues=${payload.issues?.length || 0}`);
  const cyclonedx = createCycloneDXFromXrayPayload(payload);
  const cyclonedxJson = JSON.stringify(cyclonedx, null, 2);
  
  console.log(`[INFO] Generated CycloneDX JSON: ${cyclonedxJson.length} characters`);
  console.log(`[INFO] CycloneDX serialNumber: ${cyclonedx.serialNumber}`);
  console.log(`[INFO] CycloneDX metadata.timestamp: ${cyclonedx.metadata?.timestamp}`);
  console.log(`[INFO] Components: ${cyclonedx.components?.length || 0}`);
  console.log(`[INFO] Vulnerabilities: ${cyclonedx.vulnerabilities?.length || 0}`);
  
  // Log component details to verify uniqueness
  if (cyclonedx.components && cyclonedx.components.length > 0) {
    console.log(`[INFO] Component names: ${cyclonedx.components.map((c: any) => `${c.name}@${c.version || 'unknown'}`).join(', ')}`);
  }
  
  // Log vulnerability IDs to verify uniqueness
  if (cyclonedx.vulnerabilities && cyclonedx.vulnerabilities.length > 0) {
    console.log(`[INFO] Vulnerability IDs: ${cyclonedx.vulnerabilities.map((v: any) => v.id).join(', ')}`);
  }

  // Upload CycloneDX JSON to Artifactory
  const clients = (context as any)?.clients;
  if (!clients?.platformHttp) {
    throw new Error('platformHttp is not available in context.clients.platformHttp');
  }

  // Get component name(s) from the payload using artifact.name
  let componentNames: string[] = [];
  let firstArtifactSha256: string | null = null;
  
  for (const issue of payload.issues || []) {
    for (const artifact of issue.impacted_artifacts || []) {
      // Use artifact.name and replace dots with underscores, and sanitize other special chars
      const componentName = (artifact.name || artifact.display_name || 'unknown')
        .replace(/\./g, '_')  // Replace dots with underscores
        .replace(/[:/\\]/g, '_'); // Sanitize other special characters for filename
      if (!componentNames.includes(componentName)) {
        componentNames.push(componentName);
      }
      
      // Extract SHA256 from first artifact
      if (!firstArtifactSha256 && artifact.sha256) {
        firstArtifactSha256 = artifact.sha256;
      }
    }
  }
  
  // Use first component name, or "multiple" if there are multiple components
  const componentPrefix = componentNames.length === 1 
    ? componentNames[0] 
    : componentNames.length > 1 
      ? `${componentNames[0]}_and_${componentNames.length - 1}_more`
      : 'unknown';
  
  // Simple filename format: {componentName}.cdx.json
  const filename = `${componentPrefix}.cdx.json`;
  
  // Create repository name from first two characters of SHA256
  if (!firstArtifactSha256) {
    console.warn(`[WARN] SHA256 not found in payload artifacts, cannot determine repository`);
    throw new Error('SHA256 not found in payload artifacts');
  }
  
  const repoKeyFromSha256 = firstArtifactSha256.substring(0, 2).toLowerCase();
  console.log(`[INFO] Generated repository key from SHA256: ${repoKeyFromSha256}`);
  console.log(`[INFO] Artifact SHA256: ${firstArtifactSha256}`);

  // Check if repository exists and create if it doesn't
  const repoCheckPath = `/artifactory/api/repositories/${repoKeyFromSha256}`;
  console.log(`[INFO] Checking if repository exists: ${repoCheckPath}`);

  let repositoryExists = false;
  try {
    const repoCheckRes = await clients.platformHttp.get(repoCheckPath);
    if (repoCheckRes.status === 200) {
      repositoryExists = true;
      console.log(`[INFO] Repository ${repoKeyFromSha256} already exists`);
    }
  } catch (repoCheckError: any) {
    // Repository doesn't exist if we get a 404 or similar error
    if (repoCheckError.status === 404) {
      console.log(`[INFO] Repository ${repoKeyFromSha256} does not exist, will create it`);
      repositoryExists = false;
    } else {
      console.warn(`[WARN] Error checking repository existence: ${repoCheckError.message}`);
      // Continue anyway and try to create
      repositoryExists = false;
    }
  }

  // Create repository if it doesn't exist
  if (!repositoryExists) {
    const createRepoPath = `/artifactory/api/repositories/${repoKeyFromSha256}`;
    const repoConfig = {
      key: repoKeyFromSha256,
      packageType: "Generic",
      description: "Sbom Split repo test",
      rclass: "local",
      xrayIndex: "true"
    };

    console.log(`[INFO] Creating repository: ${createRepoPath}`);
    console.log(`[INFO] Repository config: ${JSON.stringify(repoConfig, null, 2)}`);

    try {
      const createRepoRes = await clients.platformHttp.put(
        createRepoPath,
        repoConfig,
        {
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );

      if (createRepoRes.status >= 200 && createRepoRes.status < 300) {
        console.log(`[INFO] ✓ Repository ${repoKeyFromSha256} created successfully`);
      } else {
        console.warn(
          `[WARN] Repository creation returned status code: ${createRepoRes.status}`
        );
      }
    } catch (createError: any) {
      console.error(
        `[ERROR] Failed to create repository: ${createError.message}`
      );
      if (createError.status) {
        console.error(`[ERROR] Status code: ${createError.status}`);
      }
      if (createError.response?.data) {
        console.error(`[ERROR] Response: ${JSON.stringify(createError.response.data)}`);
      }
      // Continue with upload attempt even if repository creation fails
      // (it might have been created by another worker instance)
    }
  }
  
  // Upload to repository based on SHA256
  // Add SHA256 property to the URL path (format: path;sha256=value)
  const uploadPath = `artifactory/${repoKeyFromSha256}/${filename};sha256=${firstArtifactSha256}`;
  
  console.log(`[INFO] Generated filename: ${filename} (based on artifact.name from payload)`);
  console.log(`[INFO] Uploading to repository: ${repoKeyFromSha256} (based on first 2 chars of SHA256)`);
  console.log(`[INFO] SHA256 property added to upload path: ${firstArtifactSha256}`);
  
  const uploadHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    'Content-Length': cyclonedxJson.length.toString(),
  };
  if (authToken) {
    uploadHeaders['Authorization'] = `Bearer ${authToken}`;
  }
  
  console.log(`[INFO] Uploading CycloneDX JSON: ${uploadPath} (${cyclonedxJson.length} bytes)`);

  try {
    const uploadResponse = await clients.platformHttp.put(uploadPath, cyclonedxJson, {
      headers: uploadHeaders
    });
    
    const uploadStatus = uploadResponse?.status || uploadResponse?.statusCode || 0;
    if (uploadStatus >= 200 && uploadStatus < 300) {
      response.sbom = `CycloneDX SBOM generated and uploaded to Artifactory at: ${uploadPath}\n\n${cyclonedxJson}`;
      console.log(`[INFO] ✓ CycloneDX JSON uploaded successfully: ${uploadPath}`);
    } else {
      const errorBody = uploadResponse?.body || uploadResponse?.data;
      const errorText = typeof errorBody === 'string' ? errorBody : JSON.stringify(errorBody);
      console.error(`[ERROR] Upload failed. Status: ${uploadStatus}, Response: ${errorText}`);
      throw new Error(`Upload failed with status ${uploadStatus}: ${errorText}`);
    }
  } catch (uploadError: any) {
    console.error(`[ERROR] Upload failed: ${uploadError?.message || String(uploadError)}`);
    // Still return the generated JSON even if upload fails
    response.sbom = `CycloneDX SBOM generated (upload failed):\n\n${cyclonedxJson}`;
    response.message = `Upload failed: ${uploadError?.message || String(uploadError)}`;
  }


} catch (error: any) {
  console.error(`[ERROR] Worker execution failed: ${error?.message || String(error)}`);
  response.message = `Request failed: ${error?.message || String(error)}`;
}

return response;
};