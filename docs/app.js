(() => {
  'use strict';
  const el = id => document.getElementById(id);
  const tabs = {
    create: ['IMAGE STUDIO', 'Bring your stories to life.'],
    pose: ['CHARACTER LAB', 'Design an expressive character.'],
    story: ['STORYBOARD', 'Turn ideas into visual shots.'],
    timeline: ['VIDEO EDITOR', 'Edit a Short, frame by frame.'],
    assistant: ['AI ASSISTANT', 'Your creative copilot.']
  };
  const state = {assets: [], timeline: [], voice: null, music: null, selected: 0, history: []};
  const localAssetUrls = new Map();
  let backend = localStorage.getItem('va-ailock-backend') || '';
  el('backend-url').value = backend;
  const resolveBackend = path => backend + path;
  const resolveAsset = path => {
    if(!path) return '';
    if(path.startsWith('blob:')) return path;
    return backend + path;
  };
  const hasBackend = () => !!backend;
  el('backend-save').addEventListener('click', () => {
    const value = el('backend-url').value.trim().replace(/\/+$/, '');
    if(value && (!value.startsWith('https://') || !/^https:\/\/[^/]+$/i.test(value))) {
      toast('Use the HTTPS origin only, e.g. https://example.com',true); return;
    }
    backend = value;
    localStorage.setItem('va-ailock-backend',backend);
    state.assets=[]; state.timeline=[]; saveTimeline();
    refreshStatus(); loadAssets().catch(e=>toast(e.message,true)); drawTimeline();
    toast(backend ? 'Backend configured. Checking connection…' : 'Browser-only mode enabled');
  });
  const restored = (()=> { try { return JSON.parse(localStorage.getItem('va-ailock-timeline') || '[]'); } catch { return []; }})();
  if (Array.isArray(restored)) state.timeline = restored.filter(s=>s && s.asset && !String(s.asset).startsWith('local-') && Number.isFinite(+s.duration));
  const toast = (message, bad=false) => {const t=el('toast');t.textContent=message;t.className='show'+(bad?' error':'');clearTimeout(toast.timeout);toast.timeout=setTimeout(()=>t.className='',5500);};
  const api = async (url, body, file=false) => {
    let opts=body === undefined ? {} : {method:'POST',body:file?body:JSON.stringify(body)};
    if (body!==undefined && !file) opts.headers={'Content-Type':'application/json'};
    if (!hasBackend()) throw Error('This action needs a secured AI backend. The character editor works without one.');
    let res=await fetch(resolveBackend(url),opts);
    let data;try{data=await res.json()}catch{throw Error(`Server error ${res.status}`)}
    if(!res.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail || data));
    return data;
  };
  async function locked(button, task) { const before=button.textContent;button.disabled=true;button.textContent='Working…';try{await task()}catch(e){toast(e.message||String(e),true)}finally{button.disabled=false;button.textContent=before} }
  function switchTab(key){
    document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('active',b.dataset.tab===key));
    document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.id===`tab-${key}`));
    el('crumb').textContent=tabs[key][0];el('page-title').textContent=tabs[key][1];
  }
  document.querySelectorAll('.nav').forEach(b=>b.addEventListener('click',()=>switchTab(b.dataset.tab)));
  async function refreshStatus(){
    if(!hasBackend()) { el('status').innerHTML='<div class="status-row"><span>Character Lab</span><b>Ready</b></div><div class="status-row"><span>AI generation</span><b>Connect backend</b></div><div class="status-row"><span>MP4 rendering</span><b>Connect backend</b></div>'; return; }
    try {const d=await api('/api/status');
      el('status').innerHTML=`<div class="status-row"><span><i class="dot ${d.comfy_connected?'ok':''}"></i> Image engine</span><b>${d.comfy_connected && d.comfy_configured?'Ready':'Setup'}</b></div><div class="status-row"><span><i class="dot ${d.ollama_connected?'ok':''}"></i> AI assistant</span><b>${d.ollama_connected?'Ready':'Optional'}</b></div><div class="status-row"><span><i class="dot ${d.ffmpeg_connected?'ok':''}"></i> Video render</span><b>${d.ffmpeg_connected?'Ready':'Setup'}</b></div>`;
    }catch(e){el('status').textContent='Server status unavailable'}
  }
  const safeText = x => String(x).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function saveTimeline(){localStorage.setItem('va-ailock-timeline',JSON.stringify(state.timeline));el('timeline-count').textContent=state.timeline.length;}
  async function loadAssets(){
    if(hasBackend()) state.assets=await api('/api/assets');const images=state.assets.filter(a=>a.kind==='image');
    const g=el('gallery');g.innerHTML='';
    if(!images.length){g.innerHTML='<div class="empty">Your artwork will appear here.<br>Start with a generated image, an upload, or Character Lab.</div>';return;}
    for(const a of images){
      const div=document.createElement('div');div.className='galleryitem';
      div.innerHTML=`<img alt="Scene artwork" src="${resolveAsset(a.url)}"><div class="filetitle">${safeText(a.asset)}</div>`;
      const btn=document.createElement('button');btn.className='outline';btn.textContent='＋ Add to video';btn.onclick=()=>addShot(a.asset);
      div.appendChild(btn);g.appendChild(div);
    }
  }
  function addShot(asset,duration=2.0){state.timeline.push({asset,duration,motion:'slow-zoom'});state.selected=state.timeline.length-1;saveTimeline();drawTimeline();toast('Scene added to video timeline');}
  function shotUrl(asset){return localAssetUrls.get(asset) || resolveBackend(`/data/assets/${encodeURIComponent(asset)}`);}
  function drawTimeline(){
    saveTimeline();let list=el('timeline-list');list.innerHTML='';let total=state.timeline.reduce((v,x)=>v+Number(x.duration||0),0);
    el('total-duration').textContent=total.toFixed(1)+' SEC';
    if(!state.timeline.length){list.innerHTML='<div class="empty">No shots yet. Add images from the library or export your character.</div>'}
    state.timeline.forEach((s,i)=>{
      let card=document.createElement('div');card.className='shot'+(i===state.selected?' selected':'');
      card.innerHTML=`<img alt="Shot ${i+1}" src="${shotUrl(s.asset)}"><div class="shot-fields"><strong>SHOT ${String(i+1).padStart(2,'0')}</strong><div class="shot-controls"><input class="duration" type="number" aria-label="Shot duration seconds" min="0.4" max="20" step="0.1" value="${Number(s.duration).toFixed(1)}"><select class="motion" aria-label="Shot motion"><option value="slow-zoom" ${s.motion==='slow-zoom'?'selected':''}>Slow zoom</option><option value="static" ${s.motion==='static'?'selected':''}>Static</option></select></div></div><div class="shot-buttons"><button data-act="up" aria-label="Move shot up">↑</button><button data-act="down" aria-label="Move shot down">↓</button><button data-act="remove" aria-label="Remove shot">×</button></div>`;
      card.addEventListener('click',ev=>{if(ev.target.closest('button,input,select'))return;state.selected=i;drawTimeline();});
      card.querySelector('.duration').addEventListener('change',ev=>{s.duration=Math.max(.4,Math.min(20,Number(ev.target.value)||2));saveTimeline();drawTimeline()});
      card.querySelector('.motion').addEventListener('change',ev=>{s.motion=ev.target.value;saveTimeline()});
      card.querySelectorAll('[data-act]').forEach(b=>b.addEventListener('click',ev=>{
        const act=b.dataset.act;if(act==='remove'){state.timeline.splice(i,1);state.selected=Math.min(state.selected,state.timeline.length-1)}
        if(act==='up'&&i>0){[state.timeline[i-1],state.timeline[i]]=[state.timeline[i],state.timeline[i-1]];state.selected=i-1}
        if(act==='down'&&i<state.timeline.length-1){[state.timeline[i+1],state.timeline[i]]=[state.timeline[i],state.timeline[i+1]];state.selected=i+1}
        drawTimeline();ev.stopPropagation();
      }));list.appendChild(card);
    });
    const selected=state.timeline[state.selected];const preview=el('timeline-preview');
    if(selected){preview.src=shotUrl(selected.asset);preview.style.display='block';el('preview-placeholder').style.display='none'}
    else{preview.style.display='none';el('preview-placeholder').style.display='block'}
  }
  async function upload(file){
    if(!hasBackend()) {
      if(!file.type.startsWith('image/')) throw Error('Browser-only mode accepts images. Audio and video rendering need a backend.');
      const asset='local-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,8)+'.png';
      const url=URL.createObjectURL(file);
      localAssetUrls.set(asset,url);
      state.assets.unshift({asset,url,kind:'image'});
      return {asset,url,kind:'image'};
    }
    const form=new FormData();form.append('file',file,file.name);return api('/api/assets/upload',form,true);
  }
  el('refresh-library').onclick=()=>loadAssets().catch(e=>toast(e.message,true));
  el('upload-image').onchange=ev=>{const file=ev.target.files[0];if(!file)return;locked(el('refresh-library'),async()=>{const d=await upload(file);await loadAssets();toast('Artwork uploaded: '+d.asset)});ev.target.value=''};
  el('random-seed').onclick=()=>el('image-seed').value=Math.floor(Math.random()*900000000);
  async function generateScene(prompt=null,cam=null,exp=null){
    const data={prompt:prompt || el('image-prompt').value,character:el('image-character').value,
      location:el('image-location').value,pose:el('image-pose').value,expression:exp||el('image-expression').value,
      camera:cam||el('image-camera').value,seed:Number(el('image-seed').value)||42,
      width:768,height:1344,steps:25};
    let out=await api('/api/generate',data);await loadAssets();toast('New 2D scene generated');return out;
  }
  el('generate-image').onclick=ev=>locked(ev.currentTarget,async()=>{await generateScene()});
  el('plan-story').onclick=ev=>locked(ev.currentTarget,async()=>{
    // Browser-only mode provides an explicitly fixed, non-AI planning outline.
    const idea=el('story-text').value.trim();
    if(!idea)throw Error('Write a short story idea first');
    const count=Math.max(2,Math.min(12,Number(el('story-count').value)||5));
    const beats=['Establish the place and main character','Introduce the problem','Show a surprising reaction','Escalate the misunderstanding','Land the unexpected final punchline'];
    const cameras=['wide shot','medium shot','close-up','over-the-shoulder shot','close-up'];
    const emotions=['normal','confused','surprised','shocked','smirking'];
    const res=hasBackend()
      ? await api('/api/plan',{story:idea,count})
      : {title:'Offline shot outline (fixed template, not AI)',mode:'template',scenes:Array.from({length:count},(_,i)=>({
          duration:4,camera:cameras[Math.min(i,4)],expression:emotions[Math.min(i,4)],
          prompt:`Original premium 2D Indian cartoon scene, shot ${i+1} of ${count}. Idea: ${idea.slice(0,350)}. Beat: ${beats[Math.min(i,4)]}. Modern Chennai setting, expressive hand-drawn black outlines, cinematic composition, consistent characters and location, 9:16, no text, no watermark.`
        }))};
    const holder=el('planned-scenes');holder.innerHTML='';
    const label=document.createElement('div');label.style.gridColumn='1/-1';label.className='helper';label.textContent=`${res.title} — ${res.mode==='ollama'?'AI-planned storyboard':'Fixed template (Ollama not connected)'}`;holder.appendChild(label);
    res.scenes.forEach((s,i)=>{
      const card=document.createElement('div');card.className='storycard';
      card.innerHTML=`<div class="num">SCENE ${String(i+1).padStart(2,'0')} • ${Number(s.duration).toFixed(1)}s</div><textarea rows="5" aria-label="Scene prompt">${safeText(s.prompt)}</textarea><small>${safeText(s.camera)} · ${safeText(s.expression)}</small>`;
      const b=document.createElement('button');b.className='outline';b.textContent='Use prompt in Image Studio';b.onclick=()=>{el('image-prompt').value=card.querySelector('textarea').value;el('image-camera').value=['medium shot','close-up','wide shot','over-the-shoulder shot','low-angle shot'].includes(s.camera)?s.camera:'medium shot';switchTab('create');toast('Prompt loaded. Generate the image when ready.')};
      card.appendChild(b);holder.appendChild(card);
    });
    toast('Storyboard ready');
  });
  async function audioSelect(input,key,labelId){const f=input.files[0];if(!f)return;try{const a=await upload(f);state[key]=a.asset;el(labelId).textContent=f.name;toast('Audio uploaded')}catch(e){toast(e.message,true)}input.value='';}
  el('voice-file').onchange=e=>audioSelect(e.target,'voice','voice-name');
  el('music-file').onchange=e=>audioSelect(e.target,'music','music-name');
  el('voice-remove').onclick=()=>{state.voice=null;el('voice-name').textContent='No voiceover'};
  el('music-remove').onclick=()=>{state.music=null;el('music-name').textContent='No music'};
  el('music-volume').oninput=()=>el('music-volume-value').textContent=el('music-volume').value+'%';
  el('render-video').onclick=ev=>locked(ev.currentTarget,async()=>{
    if(!state.timeline.length)throw Error('Add at least one image to the timeline');
    if(!hasBackend()) throw Error('MP4 export needs a protected backend with FFmpeg. Export PNGs from Character Lab in browser-only mode.');
    if(state.timeline.some(s=>String(s.asset).startsWith('local-'))) throw Error('Switching to a backend requires reuploading browser-only images before rendering.');
    const result=await api('/api/video/render',{scenes:state.timeline,resolution:el('render-resolution').value,
      voice_asset:state.voice,music_asset:state.music,music_volume:Number(el('music-volume').value)/100});
    el('render-result').innerHTML=`<strong>Ready:</strong> ${result.seconds}s · ${result.resolution}<br><a href="${resolveAsset(result.url)}" download="${result.name}">↓ Download ${result.name}</a>`;
    toast('Video rendered successfully');
  });
  async function sendChat(){const message=el('chat-input').value.trim();if(!message)return;el('chat-input').value='';
    appendBubble(message,'user');let send=el('send-chat');await locked(send,async()=>{
      const out=await api('/api/assistant',{message,history:state.history});appendBubble(out.reply,'assistant');
      state.history.push({role:'user',content:message},{role:'assistant',content:out.reply});state.history=state.history.slice(-12);
    });
  }
  function appendBubble(text,who){const div=document.createElement('div');div.className='bubble '+(who==='user'?'user-bubble':'assistant-bubble');div.textContent=text;el('chat-log').appendChild(div);el('chat-log').scrollTop=el('chat-log').scrollHeight;}
  el('send-chat').onclick=sendChat;el('chat-input').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat()}};
  document.querySelectorAll('[data-chat]').forEach(b=>b.onclick=()=>{el('chat-input').value=b.dataset.chat;switchTab('assistant');el('chat-input').focus()});

  // Character Lab. Each SVG feature is live-editable and the 4K export is real raster output.
  const skinParts=['#head ellipse:nth-of-type(1)','#head ellipse:nth-of-type(2)', '#head ellipse:nth-of-type(3)'];
  function setAttr(id,attr,val){el(id).setAttribute(attr,val)}
  function updatePose(){
    ['left-arm','right-arm','left-leg','right-leg','head-tilt'].forEach(k=>{el(k+'-value').textContent=el(k).value+'°'});
    setAttr('arm-left','transform',`rotate(${el('left-arm').value} 142 278)`);
    setAttr('arm-right','transform',`rotate(${el('right-arm').value} 239 278)`);
    setAttr('leg-left','transform',`rotate(${el('left-leg').value} 171 425)`);
    setAttr('leg-right','transform',`rotate(${el('right-leg').value} 215 425)`);
    setAttr('head','transform',`rotate(${el('head-tilt').value} 191 203)`);
    const skin=el('skin').value,shirt=el('shirt').value,pants=el('trousers').value;
    document.querySelectorAll('#head ellipse:not(#eye-l):not(#eye-r):not(#pupil-l):not(#pupil-r)').forEach(p=>p.setAttribute('fill',skin));
    ['arm-left','arm-right'].forEach(k=>document.querySelectorAll('#'+k+' path,#'+k+' ellipse').forEach(n=>n.setAttribute('fill',skin)));
    document.querySelector('#head>path:first-child').setAttribute('fill',skin);
    el('torso').setAttribute('fill',shirt);
    ['leg-left','leg-right'].forEach(k=>document.querySelector('#'+k+' path:first-child').setAttribute('fill',pants));
    const eye=el('eye').value,mouth=el('mouth').value,brow=el('brow').value;
    const eyes={'normal':[10,13,4,7],happy:[11,6,4,4],wide:[14,20,5,9],sleepy:[11,5,3,3],angry:[11,8,4,5]};
    const [rx,ry,px,py]=eyes[eye];
    ['eye-l','eye-r'].forEach(k=>{setAttr(k,'rx',rx);setAttr(k,'ry',ry)});
    ['pupil-l','pupil-r'].forEach(k=>{setAttr(k,'rx',px);setAttr(k,'ry',py)});
    const mouthPath={'smile':['M166 229q28 25 53 0','none'],open:['M175 223q21-5 38 0q6 40-19 44q-22-4-19-44Z','#54282e'],grin:['M165 223Q193 254 221 223Q202 260 177 246Z','#faf5de'],frown:['M166 246q28-21 53 0','none'],flat:['M172 238h42','none']};
    const [d,fill]=mouthPath[mouth];setAttr('mouth-shape','d',d);setAttr('mouth-shape','fill',fill);
    const bs={normal:['M146 171q16-11 29-2','M209 169q16-10 28 2'],raised:['M145 160q17-15 31-2','M206 158q17-13 31 1'],angry:['M145 164l31 17','M208 181l31-17'],worried:['M145 181q16-15 30-15','M208 166q14 0 29 15']};
    setAttr('brow-l','d',bs[brow][0]);setAttr('brow-r','d',bs[brow][1]);
    ['room','street','plain'].forEach(n=>setAttr('bg-'+n,'display',el('background').value===n?'inline':'none'));
  }
  document.querySelectorAll('#tab-pose input,#tab-pose select').forEach(n=>n.addEventListener('input',updatePose));
  const presets={normal:[18,-18,8,-8,0,'normal','smile'],wave:[18,-125,6,-8,-8,'happy','grin'],point:[-80,-15,8,-8,5,'normal','smile'],run:[-55,65,-35,35,9,'wide','open'],shock:[-105,100,-12,12,0,'wide','open']};
  function applyPreset(name){const p=presets[name];['left-arm','right-arm','left-leg','right-leg','head-tilt'].forEach((id,i)=>el(id).value=p[i]);el('eye').value=p[5];el('mouth').value=p[6];updatePose()}
  el('preset').addEventListener('change',()=>applyPreset(el('preset').value));
  el('pose-reset').onclick=()=>{el('preset').value='normal';el('brow').value='normal';applyPreset('normal')};
  async function svgToPng(){
    const svg=el('character-svg').cloneNode(true);svg.setAttribute('xmlns','http://www.w3.org/2000/svg');
    svg.setAttribute('width','2160');svg.setAttribute('height','3840');
    const xml=new XMLSerializer().serializeToString(svg);
    const blob=new Blob([xml],{type:'image/svg+xml;charset=utf-8'});
    const url=URL.createObjectURL(blob);
    try{
      const img=new Image();await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=()=>reject(Error('Could not convert SVG to PNG'));img.src=url;});
      const canvas=document.createElement('canvas');canvas.width=2160;canvas.height=3840;
      const ctx=canvas.getContext('2d');ctx.drawImage(img,0,0,2160,3840);
      return await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
    }finally{URL.revokeObjectURL(url)}
  }
  el('pose-download').onclick=ev=>locked(ev.currentTarget,async()=>{
    const blob=await svgToPng();if(!blob)throw Error('PNG export failed');
    const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='VA_AILOCK_character_4k.png';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);toast('4K PNG exported');
  });
  el('pose-add').onclick=ev=>locked(ev.currentTarget,async()=>{
    const blob=await svgToPng();if(!blob)throw Error('PNG export failed');
    const d=await upload(new File([blob],'character_scene.png',{type:'image/png'}));
    await loadAssets();addShot(d.asset);toast('Pose added to your library and timeline');
  });
  updatePose();drawTimeline();refreshStatus();loadAssets().catch(e=>toast(e.message,true));
})();
