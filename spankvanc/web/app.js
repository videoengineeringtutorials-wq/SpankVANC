"use strict";
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="control-token"]').content;
let config, currentState, scteOptions, videoCodecOptions, dirty = false;
const kinds = {udp:"UDP · MPEG-TS",srt:"SRT · MPEG-TS",rtmp:"RTMP / RTMPS",youtube:"YouTube · RTMPS",decklink:"DeckLink · SDI",file:"Local MPEG-TS file"};
async function api(path, data) {
  const response = await fetch('/api/' + path, {method:data === undefined ? 'GET':'POST', headers:{'Content-Type':'application/json','X-SpankVANC-Token':token},body:data === undefined ? undefined:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Engine request failed');
  return result;
}
function notice(text, error=false){$('notice').hidden=false;$('notice').textContent=text;$('notice').className=error?'error':'';}
function make(tag, text, cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;}
function select(options,value,change,field){const el=make('select');if(field)el.dataset.field=field;Object.entries(options).forEach(([v,label])=>{const o=make('option',label);o.value=v;el.append(o);});el.value=value;el.addEventListener('change',()=>{change(el.value);markDirty();});return el;}
function label(text, control){const el=make('label',text);el.append(control);return el;}
function markDirty(){dirty=true;$('save').textContent='Save route *';}
function renderOutputs(){
  $('outputs').replaceChildren();
  config.outputs.forEach((out,index)=>{
    const policies={...scteOptions[$('input-kind').value][out.kind]};Object.keys(policies).forEach(k=>{if(k!=='strip'&&!(currentState?.capabilities.scte_runtime&&$('input-kind').value==='decklink'&&['file','udp','srt'].includes(out.kind)&&k==='convert'))policies[k]+=' · not available yet';});
    if(!(out.scte in policies))out.scte=Object.keys(policies)[0];
    const codecs=videoCodecOptions[out.kind];
    if(!(out.video_codec in codecs))out.video_codec=Object.keys(codecs)[0];
    const card=make('div',undefined,'output');const head=make('div',undefined,'output-head');
    const enabled=make('input');enabled.type='checkbox';enabled.checked=out.enabled;enabled.setAttribute('aria-label','Enable '+out.name);enabled.addEventListener('change',()=>{out.enabled=enabled.checked;markDirty();});
    const name=make('input');name.type='text';name.value=out.name;name.maxLength=100;name.setAttribute('aria-label','Output name');name.addEventListener('input',()=>{out.name=name.value;markDirty();});
    const remove=make('button','×','remove');remove.title='Remove output';remove.setAttribute('aria-label','Remove '+out.name);remove.disabled=config.outputs.length===1;remove.onclick=()=>{config.outputs.splice(index,1);markDirty();renderOutputs();};
    head.append(make('span',String(index+1).padStart(2,'0'),'output-number'),enabled,name,remove);card.append(head);
    card.append(label('Output type',select(kinds,out.kind,value=>{out.kind=value;out.address='';delete out.youtube_server;delete out.youtube_stream_key;if(value==='youtube'){out.youtube_server='rtmps://a.rtmps.youtube.com:443/live2';out.youtube_stream_key='';}renderOutputs();},'kind')));
    if(out.kind==='youtube'){
      const server=make('input');server.type='url';server.value=out.youtube_server||'rtmps://a.rtmps.youtube.com:443/live2';server.dataset.field='youtube_server';server.autocomplete='off';server.spellcheck=false;
      const key=make('input');key.type='password';key.value=out.youtube_stream_key||'';key.dataset.field='youtube_stream_key';key.autocomplete='off';key.spellcheck=false;key.placeholder='Paste your YouTube stream key';
      const update=()=>{out.youtube_server=server.value;out.youtube_stream_key=key.value.trim();out.address=out.youtube_stream_key?server.value.trim().replace(/\/+$/,'')+'/'+out.youtube_stream_key:'';markDirty();};
      server.addEventListener('input',update);key.addEventListener('input',update);
      card.append(label('YouTube RTMPS server',server),label('YouTube stream key · hidden for privacy',key));
      card.append(make('p','YouTube: 1080p30 progressive SDR · H.264 14 Mbit/s CBR · 2-second keyframes · AAC stereo. The YouTube server is filled in. Paste only your stream key from YouTube Studio → Go live → Stream settings.','subtle'));
    }else{
      const address=make('input');address.value=out.address;address.type=['rtmp','srt'].includes(out.kind)?'password':'text';address.autocomplete='off';address.spellcheck=false;address.placeholder=out.kind==='decklink'?'DeckLink output device name':out.kind==='file'?'/path/to/output.ts':out.kind+'://host:port';address.addEventListener('input',()=>{out.address=address.value;markDirty();});
      card.append(label('Destination'+(['rtmp','srt'].includes(out.kind)?' · hidden for privacy':''),address));
    }
    const encoding=make('div',undefined,'form-grid');
    const audio=make('input');audio.readOnly=true;audio.value=out.kind==='decklink'?'Embedded PCM':['rtmp','youtube'].includes(out.kind)?'AAC-LC · FLV':'AAC-LC · ADTS';audio.setAttribute('aria-label','Audio codec');
    encoding.append(label('Video codec',select(codecs,out.video_codec,value=>out.video_codec=value,'video_codec')),label('Audio codec',audio));card.append(encoding);
    if(['rtmp','youtube'].includes(out.kind))card.append(make('p','RTMP uses FLV: H.264 + AAC. MPEG-2 video is available on TS outputs.','subtle'));
    const grid=make('div',undefined,'form-grid');grid.append(label('Captions',select({pass:'Pass through',strip:'Strip',recaption:'audioWhisper · replace'},out.captions,value=>out.captions=value,'captions')),label('SCTE signaling',select(policies,out.scte,value=>out.scte=value,'scte')));card.append(grid);$('outputs').append(card);
  });
}
function renderSource(){
  const deck=$('input-kind').value==='decklink';
  $('source-address-label').hidden=deck;$('decklink-source').hidden=!deck;
  $('input-realtime').parentElement.hidden=deck;
  if(!deck)return;
  const devices=(currentState?.capabilities.decklink_devices||[]).filter(d=>d.input);
  const pick=$('decklink-device');pick.replaceChildren();
  const empty=make('option','Choose a Blackmagic input…');empty.value='';pick.append(empty);
  devices.forEach(d=>{const o=make('option',d.name);o.value=d.name;pick.append(o);});
  const saved=$('input-address').value;
  if(saved&&!devices.some(d=>d.name===saved)){const o=make('option',saved+' (unavailable)');o.value=saved;pick.append(o);}
  pick.value=saved;
  const device=devices.find(d=>d.name===saved), modes=$('decklink-mode');modes.replaceChildren();
  const placeholder=make('option','Choose the source video mode…');placeholder.value='';modes.append(placeholder);
  (device?.modes||[]).forEach(m=>{const o=make('option',m.name+' · '+m.code);o.value=m.code;modes.append(o);});
  modes.value=config.input.format_code||'';
  if(modes.selectedIndex<0)modes.value='';
  const compatibility=currentState?.capabilities.decklink_profile==='compatibility';
  $('source-capability-note').textContent=compatibility?'Existing FFmpeg compatibility mode: SDI video/audio and the captions supported by that build. Select SCTE Strip. Live monitoring and SCTE conversion require the SpankVANC FFmpeg extensions.':'DeckLink input captures SDI video, embedded stereo audio and captions. Program SCTE-104 cues can convert to SCTE-35 for TS outputs. SDI output remains unavailable.';
  $('decklink-info').textContent=compatibility?'Device and modes listed by your FFmpeg. Choose the actual Duo port; no Duo 2 profiles are assumed.':currentState?.capabilities.decklink_input
    ? 'SDI input · embedded stereo audio · 608/708 caption capture. 1080i59.94 uses mode Hi59.'
    : (currentState?.capabilities.decklink_error||'Live capture needs the DeckLink-enabled FFmpeg build.');
}
function fill(cfg){
  config=structuredClone(cfg);
  $('scte-error-policy').value=cfg.input.scte_error_policy||'continue';$('route-name').value=cfg.name;$('input-kind').value=cfg.input.kind;$('input-address').value=cfg.input.address;$('input-realtime').checked=cfg.input.realtime;
  $('whisper-model').value=cfg.whisper.model;$('whisper-language').value=cfg.whisper.language;$('whisper-delay').value=cfg.whisper.delay_ms;$('whisper-channel').value=cfg.whisper.audio_channel;
  $('gpo-enabled').checked=cfg.gpo.enabled;$('gpo-port').value=cfg.gpo.port;$('gpo-channel').value=cfg.gpo.channel;$('gpo-pulse').value=cfg.gpo.pulse_ms;renderSource();renderOutputs();
}
function collect(){
  config.name=$('route-name').value;config.input={kind:$('input-kind').value,address:$('input-address').value,realtime:$('input-realtime').checked,format_code:$('decklink-mode').value||'',scte_error_policy:$('scte-error-policy').value};
  config.whisper={model:$('whisper-model').value,language:$('whisper-language').value,delay_ms:Number($('whisper-delay').value),audio_channel:Number($('whisper-channel').value)};
  config.gpo={enabled:$('gpo-enabled').checked,port:$('gpo-port').value,baud:115200,channel:Number($('gpo-channel').value),pulse_ms:Number($('gpo-pulse').value)};return structuredClone(config);
}
function renderPlan(plan){
  $('ready-tag').textContent=plan.ready?'READY':'ACTION NEEDED';$('blockers').replaceChildren();
  if(plan.ready)$('blockers').append(make('div','Route is ready to start.','success'));
  plan.blockers.forEach(text=>$('blockers').append(make('div',text,'blocker')));
  $('plan-outputs').replaceChildren();plan.outputs.forEach(out=>{const row=make('div',undefined,'plan-output');row.append(make('strong',out.name),make('span',out.container+' / CC: '+out.captions+' / '+out.scte_label));$('plan-outputs').append(row);});
  $('notes').replaceChildren(...plan.notes.map(text=>make('li',text)));
}
function renderState(state){
  currentState=state;$('route-status').textContent=state.running?'Route running':state.last_exit!==null&&state.last_exit!==0&&!state.stopped_by_user?'Route stopped · check log':'Engine idle';$('state-dot').className='dot'+(state.running?' lime':'');
  $('start').disabled=state.running;$('stop').disabled=!state.running;$('save').disabled=state.running;$('refresh-devices').disabled=state.running;
  document.querySelectorAll('main input,main select:not(#caption-service),#add-output,.remove').forEach(el=>el.disabled=state.running);
  $('exit-code').textContent=state.running?'RUNNING':state.last_exit===null?'IDLE':state.stopped_by_user?'STOPPED':'EXIT '+state.last_exit;
  const log=$('logs');const bottom=log.scrollTop+log.clientHeight>=log.scrollHeight-30;log.textContent=state.logs.join('\n')||'No route started. Configure your source and check readiness.';if(bottom)log.scrollTop=log.scrollHeight;
  const cap=state.capabilities;$('capabilities').replaceChildren();
  [['FFmpeg',!!cap.ffmpeg],['H.264 / libx264',cap.libx264],['MPEG-2 video',cap.mpeg2video],['AAC audio',cap.aac],['SRT transport',cap.srt],['RTMP transport',cap.rtmp],['DeckLink SDI capture',cap.decklink_input],['DeckLink device discovery',!!cap.decklink_devices?.length],['SCTE-104 → 35',cap.scte_runtime],['Live caption monitor',cap.source_monitor],['TSDuck',!!cap.tsp]].forEach(([name,yes])=>{const row=make('div',undefined,'cap-row');row.append(make('span',name),make('span',yes?'AVAILABLE':'NOT READY',yes?'yes':''));$('capabilities').append(row);});
  $('ffmpeg-version').textContent=cap.version||'FFmpeg not found';renderMonitor({monitor:state.source_monitor,running:state.running,monitor_running:state.monitor_running});
}
let latestMonitor;
function renderMonitor(data){
  if(!data?.monitor)return;
  latestMonitor=data;const m=data.monitor,service=$('caption-service').value;
  const status={stopped:'STOPPED',waiting:'WAITING FOR INPUT',stale:'SOURCE DATA STALE',receiving:'LIVE INPUT',no_signal:'NO SDI SIGNAL'};
  const supported=!!currentState?.capabilities.source_monitor;
  $('caption-status').textContent=supported?(status[m.status]||m.status):'EXTENDED FFMPEG REQUIRED';
  $('caption-screen').textContent=!supported?'This FFmpeg does not include SpankVANC live-caption telemetry. Caption pass/strip on outputs uses the capabilities of your existing build.':m.services[service]||(m.status==='stopped'?'Start the source monitor or a DeckLink route to view incoming captions.':m.status==='no_signal'?'No SDI signal.':m.status==='stale'?'Caption monitor data is stale.':'Waiting for displayable '+service+' caption text…');
  $('caption-counts').textContent=`${m.source?.name||'Source'} ${m.source?.mode||''} · ${m.frames} frames · ${m.caption_triplets} 608 pairs · ${m.digital_triplets} 708 triplets · ${m.invalid_triplets} invalid pairs`;
  $('cue-counts').textContent=`SCTE-104: ${m.scte104_packets} ANC packets · Converted: ${m.converted} commands`+(m.rejected?` · REJECTED: ${m.rejected} — ${data.running?'A/V running; see rejected messages':'see rejected messages'}`:m.conversion_error?' · CONVERSION ERROR — see engine log':'');
  $('scte-rejections').textContent=(m.rejections||[]).map(r=>`[${r.received_at}] ${r.reason}\nSource ${(r.source_pts90k/90000).toFixed(3)}s · rejected total ${r.total}\nANC: ${r.payload_hex}`).join('\n\n')||'No rejected messages.';
  $('cue-counts').classList.toggle('caption-error',m.conversion_error);
  $('caption-history').textContent=m.history.filter(h=>h.service===service).slice(-20).map(h=>`[${(h.pts90k/90000).toFixed(2)}s] ${h.text}`).join('\n\n')||'No decoded text yet.';
  $('monitor-start').disabled=data.running||data.monitor_running||!currentState?.capabilities.source_monitor;
  $('monitor-stop').disabled=!data.monitor_running;
}
$('caption-service').onchange=()=>renderMonitor(latestMonitor);
$('monitor-start').onclick=async()=>{try{const state=await api('monitor/start',collect());renderState(state);notice('Source monitor started locally.');}catch(error){notice(error.message,true);}};
$('monitor-stop').onclick=async()=>{try{const state=await api('monitor/stop',{});renderState(state);notice('Source monitor stopped.');}catch(error){notice(error.message,true);}};
setInterval(async()=>{if(!config)return;try{renderMonitor(await api('monitor'));}catch{}},500);
async function action(path){try{const result=await api(path,path==='stop'?{}:collect());if(path==='plan'){renderPlan(result);notice(result.ready?'Preflight passed. You can start the route.':'Preflight found items that need attention.');}else{dirty=false;$('save').textContent='Save route';renderState(result);renderPlan(result.plan);notice(path==='save'?'Route saved locally.':path==='start'?'Route started. Monitor the log and receiving output.':'Route stopped.');}}catch(error){notice(error.message,true);}}
$('save').onclick=()=>action('save');$('validate').onclick=()=>action('plan');$('start').onclick=()=>action('start');$('stop').onclick=()=>action('stop');
$('add-output').onclick=()=>{if(config.outputs.length>=8)return notice('Maximum eight outputs in this prototype.',true);let n=1;while(config.outputs.some(out=>out.name==='Output '+n))n++;config.outputs.push({name:'Output '+n,kind:'udp',address:'',captions:'pass',scte:'strip',enabled:true});markDirty();renderOutputs();};
document.querySelectorAll('.source input,.source select,.tools input,.tools select').forEach(el=>el.addEventListener('input',markDirty));
$('input-kind').addEventListener('change',()=>{$('input-address').value='';config.input.format_code='';renderSource();renderOutputs();});
$('decklink-device').addEventListener('change',()=>{$('input-address').value=$('decklink-device').value;config.input.format_code='';renderSource();markDirty();});
$('decklink-mode').addEventListener('change',()=>{config.input.format_code=$('decklink-mode').value;markDirty();});
$('refresh-devices').onclick=async()=>{try{const state=await api('devices',{});currentState=state;renderSource();renderState(state);notice('Device list refreshed.');}catch(error){notice(error.message,true);}};
async function boot(){try{const state=await api('state');scteOptions=state.scte_options;videoCodecOptions=state.video_codec_options;currentState=state;fill(state.config);renderState(state);renderPlan(state.plan);}catch(error){notice(error.message,true);$('route-status').textContent='Engine unavailable';}}
boot();
setInterval(async()=>{try{const state=await api('state');if(!config)return;renderState(state);}catch(error){$('route-status').textContent='Engine unavailable';}},2000);
