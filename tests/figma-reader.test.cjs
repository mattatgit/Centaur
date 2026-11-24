const {test} = require('node:test');
const assert = require('node:assert/strict');
const {resolve, reference} = require('../integrations/figma/broker.cjs');
const url='https://www.figma.com/design/FILE/branch/BRANCH/Test?node-id=23-19&t=x';
const input={project:'test-project',operation:'design',urls:[url]};
test('read the authorised branch node and its rendered artwork without CDN credentials',async()=>{
  const calls=[];
  const image=Buffer.from('89504e470d0a1a0a','hex');
  const fetch=async(location,options)=>{
    const target=new URL(location); calls.push(target);
    assert.equal(options.redirect,'error');
    if(target.hostname==='s3-alpha.figma.com') {
      assert.equal(options.headers,undefined); return new Response(image);
    }
    assert.equal(options.headers['X-Figma-Token'],'fixture');
    if(target.pathname==='/v1/files/BRANCH/nodes') return Response.json({name:'Example',nodes:{'23:19':{document:{id:'23:19',type:'FRAME',name:'Screen'}}}});
    assert.equal(target.pathname,'/v1/images/BRANCH');return Response.json({images:{'23:19':'https://s3-alpha.figma.com/art'}});
  };
  const result=await resolve(input,{'test-project':['BRANCH']},'fixture',fetch);
  assert.equal(result.results[0].design.nodes[0].name,'Screen');
  assert.equal(result.results[0].png,image.toString('base64'));
  assert.equal(calls[0].searchParams.get('ids'),'23:19');
});
test('deny ungranted projects and unsupported links before contacting Figma',async()=>{
  let contacted=false;
  await assert.rejects(resolve(input,{foreign:['BRANCH']},'fixture',()=>{contacted=true}),/not been authorised/);
  assert.equal(contacted,false);
  assert.throws(()=>reference('https://www.figma.com.example/design/FILE'));
});
test('permission errors contain no credentials',async()=>{
  await assert.rejects(resolve(input,{'test-project':['BRANCH']},'secret-fixture',async()=>new Response('',{status:403})),
    error=>/denied/.test(error.message) && !error.message.includes('secret-fixture'));
});
