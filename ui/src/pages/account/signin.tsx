import Carousel from "@/components/Account/Carousel";
import SignIn from "@/components/Account/SignIn";

export default function App(props: any) {
  return (
    <>
      {true && (
        <div className="flex bg-neutral-100 dark:bg-dark text-neutral-700 dark:text-neutral-200 w-screen h-screen">
          <div className="hidden md:block w-1/2 h-full">
            <Carousel {...props} />
          </div>
          <div className="w-screen md:h-screen md:pb-0 md:w-1/2 grid place-items-center">
            <SignIn />
          </div>
        </div>
      )}
    </>
  );
}
