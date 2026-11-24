const MAX_RESPONSE_BYTES = 32 * 1024 * 1024;
const REQUEST_TIMEOUT_MS = 30_000;

class FigmaError extends Error {
  constructor(status, message) {
    super(message);
    this.name = 'FigmaError';
    this.status = status;
  }
}

function parseFigmaUrl(input) {
  if (typeof input !== 'string' || !input.trim()) {
    throw new FigmaError(400, 'Provide a Figma design or file URL.');
  }

  const original = input.trim();
  // WHATWG URL normalizes dot segments (including %2e variants), so reject
  // those before parsing rather than accepting a disguised file path.
  if (/(?:^|\/)(?:\.|%2e){1,2}(?:\/|[?#]|$)/i.test(original)) {
    throw new FigmaError(400, 'Provide a Figma design or file URL with a valid path.');
  }
  let url;
  try {
    url = new URL(original);
  } catch {
    throw new FigmaError(400, 'Provide a valid Figma design or file URL.');
  }

  if (url.protocol !== 'https:' || !['figma.com', 'www.figma.com'].includes(url.hostname) ||
      url.username || url.password || url.port || url.hash) {
    throw new FigmaError(400, 'Only HTTPS figma.com design and file URLs are supported.');
  }

  // Limit the path to the public file-link forms, not arbitrary Figma pages or API URLs.
  const match = /^\/(design|file)\/([a-zA-Z0-9]+)(?:\/([^/]+))?\/?$/.exec(url.pathname);
  if (!match || (match[3] && /%(?:2f|5c|0[0-9a-f]|1[0-9a-f]|7f)/i.test(match[3]))) {
    throw new FigmaError(400, 'Provide a Figma design or file URL with a valid file key.');
  }

  const ids = url.searchParams.getAll('node-id');
  if (ids.length > 1 || (ids.length === 1 && !/^\d+[:-]\d+$/.test(ids[0]))) {
    throw new FigmaError(400, 'The Figma node-id must identify one frame or node.');
  }

  const nodeId = ids.length ? ids[0].replace('-', ':') : null;
  const fileKey = match[2];
  const canonical = new URL(`https://www.figma.com/${match[1]}/${fileKey}`);
  if (nodeId) canonical.searchParams.set('node-id', nodeId.replace(':', '-'));
  return { url: canonical.href, fileKey, nodeId };
}

function restError(response) {
  switch (response.status) {
    case 400:
      return new FigmaError(400, 'Figma rejected the file or node request.');
    case 401:
    case 403:
      return new FigmaError(response.status, 'Figma access was denied. Check FIGMA_ACCESS_TOKEN and file permissions.');
    case 404:
      return new FigmaError(404, 'Figma could not find this file or node, or access is restricted.');
    case 429: {
      const retryAfter = response.headers?.get?.('retry-after');
      // Never echo arbitrary response headers into application errors.
      const delay = retryAfter && /^\d{1,8}$/.test(retryAfter) ? ` Retry after ${retryAfter} seconds.` : '';
      return new FigmaError(429, `Figma rate limit reached.${delay}`);
    }
    default:
      return new FigmaError(response.status >= 400 && response.status < 500 ? response.status : 502, 'Figma could not complete the read request.');
  }
}

async function readBoundedJson(response) {
  const declaredLength = Number(response.headers?.get?.('content-length'));
  if (declaredLength > MAX_RESPONSE_BYTES) {
    await response.body?.cancel?.();
    throw new FigmaError(502, 'Figma response is too large to read safely.');
  }

  if (!response.body?.getReader) {
    throw new FigmaError(502, 'Figma returned an invalid JSON response.');
  }
  const reader = response.body.getReader();
  const chunks = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > MAX_RESPONSE_BYTES) {
        await reader.cancel();
        throw new FigmaError(502, 'Figma response is too large to read safely.');
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  const bytes = Buffer.concat(chunks, length);

  try {
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
  } catch {
    throw new FigmaError(502, 'Figma returned an invalid JSON response.');
  }
}

async function readFigma(input, { token = process.env.FIGMA_ACCESS_TOKEN, fetchImpl = globalThis.fetch } = {}) {
  const reference = parseFigmaUrl(input);
  if (typeof token !== 'string' || !token.trim()) {
    throw new FigmaError(503, 'Set FIGMA_ACCESS_TOKEN to read Figma designs.');
  }

  const endpoint = new URL(`https://api.figma.com/v1/files/${reference.fileKey}`);
  if (reference.nodeId) {
    endpoint.pathname += '/nodes';
    endpoint.searchParams.set('ids', reference.nodeId);
  } else {
    endpoint.searchParams.set('depth', '2');
  }

  let response;
  try {
    response = await fetchImpl(endpoint.href, {
      method: 'GET',
      headers: { 'X-Figma-Token': token.trim(), Accept: 'application/json' },
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      redirect: 'error'
    });
    if (!response.ok) throw restError(response);
    const data = await readBoundedJson(response);
    if (reference.nodeId && (!data?.nodes || !data.nodes[reference.nodeId])) {
      throw new FigmaError(404, 'Figma could not find this node in the file.');
    }
    return { reference, data };
  } catch (error) {
    if (error instanceof FigmaError) throw error;
    if (error?.name === 'TimeoutError' || error?.name === 'AbortError') {
      throw new FigmaError(504, 'Figma did not respond in time.');
    }
    throw new FigmaError(502, 'Could not reach Figma.');
  } finally {
    if (response && !response.ok) await response.body?.cancel?.().catch(() => {});
  }
}

module.exports = { FigmaError, parseFigmaUrl, readFigma };
