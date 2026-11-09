import { ref } from 'vue'
import { errorText } from './api'

export function useAction() {
  const busy = ref(false), error = ref('')
  async function run(fn:()=>Promise<void>) {
    if (busy.value) return
    busy.value=true; error.value=''
    try { await fn() } catch(e) { error.value=errorText(e) } finally { busy.value=false }
  }
  return {busy,error,run}
}
export function retryKey() {
  let last = '', id = ''
  return {
    for(payload:object) {
      const value=JSON.stringify(payload)
      if(!id || last!==value) { id=Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);last=value }
      return id
    },
    clear(){id=''}
  }
}
export const dateTime=(s:number)=>new Date(s*1000).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})
