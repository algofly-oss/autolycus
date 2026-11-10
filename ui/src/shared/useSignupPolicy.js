import {useEffect,useState} from 'react';
import axios from 'axios';
import apiRoutes from '@/shared/routes/apiRoutes';

export default function useSignupPolicy() {
  const [policy,setPolicy]=useState({loading:true,enabled:false,error:false});
  useEffect(()=>{
    const controller=new AbortController();
    axios.get(apiRoutes.authSettings,{signal:controller.signal}).then(({data})=>{
      if(!controller.signal.aborted)setPolicy({loading:false,enabled:data.signup_enabled===true,error:false});
    }).catch(()=>{if(!controller.signal.aborted)setPolicy({loading:false,enabled:false,error:true});});
    return()=>controller.abort();
  },[]);
  return policy;
}
