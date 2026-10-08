import {vi} from 'vitest';
import {collections,type MediaItem,type Overview} from '../types';
import {resetSession} from '../api/client';
export const makeItem=(id:string,kind:MediaItem['kind']='movies',status:MediaItem['status']='pending'):MediaItem=>({id,source_id:'source',path:`C:\\Incoming\\${id}.mkv`,kind,status,signature:{size:100},metadata:{title:id,year:'2016'},decision:null});
export function mockApi(items:MediaItem[]=[],overrides:Record<string,unknown>={}){
 resetSession();
 const overview:Overview={counts:Object.fromEntries(Object.keys(collections).map(k=>[k,items.filter(i=>i.kind===k).length])) as Overview['counts'],status_counts:{},total:items.length,review:items.filter(i=>['pending','no_match','error'].includes(i.status)).length,indexed_bytes:items.length*100,sources:1,destinations:1,jobs_running:0};
 const requests:{path:string;method:string;body:unknown}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(input:string|URL|Request,init?:RequestInit)=>{
  const u=new URL(String(input),'http://localhost');const path=u.pathname.replace('/api/v1','');const method=init?.method??'GET';const body=init?.body?JSON.parse(String(init.body)):null;requests.push({path,method,body});
  let value:unknown=overrides[method+' '+path]??overrides[path];
  if(value instanceof Error)throw value;
  if(value===undefined){if(path==='/session')value={csrf_token:'test-csrf'};else if(path==='/overview')value=overview;else if(path==='/settings')value={theme:'ivory',view:'grid',providers:{}};else if(path==='/items') {let found=items.filter(i=>(!u.searchParams.get('kind')||i.kind===u.searchParams.get('kind'))&&(!u.searchParams.get('query')||JSON.stringify(i).toLowerCase().includes(u.searchParams.get('query')!.toLowerCase()))&&(!u.searchParams.get('status')||(u.searchParams.get('status')==='review'?['pending','error','no_match'].includes(i.status):i.status===u.searchParams.get('status'))));const offset=Number(u.searchParams.get('offset')??0),limit=Number(u.searchParams.get('limit')??100);value={items:found.slice(offset,offset+limit),total:found.length,offset,limit};}else if(path.endsWith('/candidates'))value={items:[],state:'not_checked',error:null};else if(path.endsWith('/decision'))value={...items.find(i=>path.includes(i.id)),decision:body,status:'approved'};else value=[];}
  return new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
 }));return requests;
}
