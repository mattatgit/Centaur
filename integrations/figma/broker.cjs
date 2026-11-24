// Read one bounded request on a systemd-accepted Unix socket. The token is
// available only to this service identity, never the Centaur/OMP process.
const fs = require('node:fs');
const { parseFigmaUrl, readFigma, FigmaError } = require('./dialogue-reader.cjs');

function reference(url) {
  if (typeof url !== 'string' || url.length > 2048 || /[\\\x00-\x20]/.test(url)) throw new Error('Invalid Figma link.');
  // Dialogue supports the file link. For a branch the REST file key is the
  // branch key itself. Preserve the exact posted URL separately.
  const normalized = url.replace(/^(https:\/\/(?:www\.)?figma\.com\/(?:design|file)\/)\w+\/branch\/([A-Za-z0-9]+)(?=\/|\?|$)/, '$1$2');
  return parseFigmaUrl(normalized);
}

async function bytes(response, limit) {
  if (!response.ok) { await response.body?.cancel(); throw new Error('Figma could not export this artwork.'); }
  if (Number(response.headers.get('content-length')) > limit) {
    await response.body?.cancel(); throw new Error('This Figma export is too large. Select a smaller frame.');
  }
  const chunks=[]; let length=0;
  for await (const chunk of response.body) {
    length+=chunk.length;
    if (length>limit) throw new Error('This Figma export is too large. Select a smaller frame.');
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

function outline(root) {
  const result=[]; const queue=[root]; let index=0, truncated=false;
  while (index<queue.length && result.length<80) {
    const node=queue[index++];
    const view={};
    for (const key of ['id','type','name','characters','absoluteBoundingBox','cornerRadius','layoutMode','itemSpacing','style','fills','strokes']) {
      if (node[key] === undefined) continue;
      if (typeof node[key] === 'string') view[key]=node[key].slice(0,512);
      else if (Buffer.byteLength(JSON.stringify(node[key]))<=1400) view[key]=node[key];
    }
    result.push(view);
    if (Buffer.byteLength(JSON.stringify(result))>24000) { result.pop(); truncated=true; break; }
    for (const child of node.children || []) {
      if (queue.length>=160) { truncated=true; break; }
      queue.push(child);
    }
  }
  return {nodes:result,truncated:truncated || index<queue.length};
}

async function resolve(input, grants, token, fetchImpl=fetch) {
  if (!['title','design'].includes(input.operation) || !Array.isArray(input.urls) ||
      input.urls.length<1 || input.urls.length>8 || typeof input.project!=='string')
    throw new Error('Invalid design request.');
  const refs=input.urls.map(reference);
  if (!Object.hasOwn(grants,input.project) || refs.some(r=>!grants[input.project].includes(r.fileKey)))
    throw new Error('This Figma file has not been authorised for this project on this machine.');
  const results=[]; let artworkBytes=0;
  for (const ref of refs) {
    const { data } = await readFigma(ref.url,{token,fetchImpl});
    const entry={name:String(data.name || '').slice(0,120)};
    if (input.operation==='design') {
      const root=ref.nodeId ? data.nodes[ref.nodeId].document : data.document;
      const target=ref.nodeId ? root : root?.children?.flatMap(p=>p.children || []).find(n=>n.visible!==false);
      if (!target?.id) throw new Error('Select a visible Figma frame or component for this reference.');
      entry.selectedNode=target.id;
      entry.design=outline(target);
      const size=target.absoluteBoundingBox || {};
      const scale=Math.max(.01,Math.min(1,1536/Math.max(size.width || 1,size.height || 1)));
      const render=new URL('https://api.figma.com/v1/images/'+ref.fileKey);
      render.search=new URLSearchParams({ids:target.id,format:'png',scale:String(scale)}).toString();
      const metadata=await bytes(await fetchImpl(render,{headers:{'X-Figma-Token':token},redirect:'error',signal:AbortSignal.timeout(12000)}),32768);
      const location=JSON.parse(metadata).images?.[target.id];
      if (!location) throw new Error('Figma did not return an image for this selection.');
      const asset=new URL(location);
      if (asset.protocol!=='https:' || asset.username || asset.password || asset.port ||
          !/^(?:s3-alpha(?:-sig)?\.figma\.com|figma-alpha-api\.s3(?:[.-][a-z0-9-]+)?\.amazonaws\.com)$/.test(asset.hostname))
        throw new Error('Figma returned an unsupported artwork location.');
      // The CDN request deliberately carries no authentication header.
      const image=await bytes(await fetchImpl(asset,{redirect:'error',signal:AbortSignal.timeout(12000)}),1024*1024);
      artworkBytes+=image.length;
      if (artworkBytes>3*1024*1024 || !image.subarray(0,8).equals(Buffer.from('89504e470d0a1a0a','hex')))
        throw new Error('The Figma artwork exceeds the request limit or is not a PNG.');
      entry.png=image.toString('base64');
    }
    results.push(entry);
  }
  return {results};
}

async function main() {
  let request=Buffer.alloc(0);
  const chunk=Buffer.alloc(4096);
  while (!request.includes(10)) {
    const count=fs.readSync(0,chunk,0,chunk.length);
    if (!count || request.length+count>24000) throw new Error('Invalid design request.');
    request=Buffer.concat([request,chunk.subarray(0,count)]);
  }
  const token=fs.readFileSync(process.env.CREDENTIALS_DIRECTORY+'/figma','utf8').trim();
  const grants=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
  return resolve(JSON.parse(request.toString()),grants,token);
}

if (require.main===module) main().then(value=>process.stdout.write(JSON.stringify(value)+'\n')).catch(error=>{
  const safe = error instanceof FigmaError || (error instanceof Error && !error.code && !['SyntaxError','TypeError','TimeoutError'].includes(error.name));
  process.stdout.write(JSON.stringify({error:safe ? error.message.slice(0,240) : 'Could not read the design. Check the Figma service and file access.'})+'\n');
});
module.exports={reference,resolve};
