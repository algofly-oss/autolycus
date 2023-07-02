import { useEffect } from "react";
import Carousel from "@/components/Account/Carousel";
import SignUp from "@/components/Account/SignUp";
import useAuth from "@/shared/hooks/useAuth";
import uiRoutes from "@/shared/routes/uiRoutes";

export default function App(props: any) {
  const auth = useAuth();

  useEffect(() => {
    auth.autoRoute(uiRoutes.signUp);
  }, []);

  return (
    <div className="flex bg-neutral-100 dark:bg-dark text-neutral-700 dark:text-neutral-200 w-screen h-screen">
      <div className="hidden md:block w-1/2 h-full">
        <Carousel />
      </div>
      <div className="w-screen md:h-screen md:pb-0 md:w-1/2 grid place-items-center">
        <SignUp />
      </div>
    </div>
  );
}
