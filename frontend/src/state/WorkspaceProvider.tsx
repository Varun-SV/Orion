import {createContext,useCallback,useContext,useEffect,useState,type ReactNode,type Dispatch,type SetStateAction} from 'react';
import {api,json} from '../api/client';
import type {Overview,Settings} from '../types';
interface Workspace {selected:string[];setSelected:Dispatch<SetStateAction<string[]>>;overview:Overview|null;settings:Settings|null;loading:boolean;error:string;revision:number;refresh:()=>void;saveSettings:(updates:Partial<Settings>)=>Promise<void>}
const Context=createContext<Workspace|null>(null);
export function WorkspaceProvider({children}:{children:ReactNode}){
 const [selected,setSelected]=useState<string[]>([]);
 const [overview,setOverview]=useState<Overview|null>(null),[settings,setSettings]=useState<Settings|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState(''),[revision,setRevision]=useState(0);
 const refresh=useCallback(()=>setRevision(n=>n+1),[]);
 useEffect(()=>{let current=true;Promise.all([api<Overview>('/overview'),api<Settings>('/settings')]).then(([o,s])=>{if(current){setOverview(o);setSettings(s);setError('');}}).catch(e=>{if(current)setError(e.message);}).finally(()=>{if(current)setLoading(false);});return()=>{current=false;};},[revision]);
 useEffect(()=>{if(settings)document.documentElement.dataset.theme=settings.theme;},[settings]);
 const saveSettings=useCallback(async(updates:Partial<Settings>)=>{const saved=await api<Settings>('/settings',json('PUT',updates));setSettings(saved);refresh();},[refresh]);
 return <Context.Provider value={{selected,setSelected,overview,settings,loading,error,revision,refresh,saveSettings}}>{children}</Context.Provider>;
}
export function useWorkspace(){const context=useContext(Context);if(!context)throw new Error('Workspace provider required');return context;}
