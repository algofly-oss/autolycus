import {useEffect,useLayoutEffect} from 'react';

// Measure client layouts before paint without running layout effects during SSR.
const useBrowserLayoutEffect=typeof window==='undefined'?useEffect:useLayoutEffect;
export default useBrowserLayoutEffect;
