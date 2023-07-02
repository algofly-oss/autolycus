import Link from "next/link";
import TextBox from "@/shared/components/TextBox";
import reactState from "@/shared/hooks/reactState";
import useAuth from "@/shared/hooks/useAuth";
import uiRoutes from "@/shared/routes/uiRoutes";
import GoBack from "./GoBack";
import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { MdLockOutline, MdOutlineMailOutline } from "react-icons/md";
import { FcGoogle } from "react-icons/fc";

export default function SignUp() {
  const auth = useAuth();

  const router = useRouter();
  const data = reactState();
  const error = reactState();
  const [signUpProgress, setSignUpProgress] = useState(false);

  const validateAllInputs = () => {
    let allOk = true;

    if (!data.get("name")) {
      error.set("name", "Please enter your name");
      allOk = false;
    } else {
      error.set("name", "");
    }

    if (!data.get("username")) {
      error.set("username", "Please enter your email");
      allOk = false;
    } else {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(data.get("username"))) {
        error.set("username", "Please enter a valid email");
        allOk = false;
      } else {
        error.set("username", "");
      }
    }

    if (!data.get("password")) {
      error.set("password", "Please enter your password");
      allOk = false;
    } else {
      const passwordRegex =
        /^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[^a-zA-Z0-9]).{8,}$/;
      if (!passwordRegex.test(data.get("password"))) {
        error.set(
          "password",
          "Password must be at least 8 characters long, contain at least 1 uppercase letter, 1 lowercase letter, and 1 number"
        );
        allOk = false;
      } else {
        error.set("password", "");
      }
    }

    return allOk;
  };

  const handleSignUp = async () => {
    if (!validateAllInputs()) {
      return;
    }

    auth.signOut();
    error.set("username", "");
    error.set("password", "");
    setSignUpProgress(true);

    const msg = await auth.signUp(
      data.get("name"),
      data.get("username"),
      data.get("password")
    );

    switch (msg) {
      case "success":
        setSignUpProgress(false);
        auth.autoRoute();
        break;
      default:
        setSignUpProgress(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.code === "Enter") {
      handleSignUp();
    }
  };

  return (
    <div className="rounded-lg p-6 lg:p-16 w-full 2xl:w-[45rem]">
      <GoBack />
      <p className="text-3xl font-bold">Create Account</p>
      <p className="mb-6">Please enter your details</p>
      <TextBox
        label="Name"
        icon={<MdOutlineMailOutline size={20} />}
        placeholder="Enter your name"
        value={data.get("name")}
        setValue={(val) => data.set("name", val)}
        error={error.get("name")}
      />
      <TextBox
        label="Email"
        icon={<MdOutlineMailOutline size={20} />}
        placeholder="Enter your email"
        value={data.get("username")}
        setValue={(val) => data.set("username", val)}
        error={error.get("username")}
      />
      <TextBox
        label="Password"
        icon={<MdLockOutline size={20} />}
        placeholder="Enter your password"
        value={data.get("password")}
        setValue={(val) => data.set("password", val)}
        error={error.get("password")}
        mask={true}
        onKeyDown={handleKeyPress}
      />

      {/* <Link href={uiRoutes.forgotPassword} passHref>
        <p className="text-right my-2 font-medium cursor-pointer text-sm text-blue-500">
          Forgot password
        </p>
      </Link> */}
      <button
        className="flex items-center justify-center bg-blue-500 dark:bg-blue-700 text-white w-full p-3 rounded-md text-sm md:text-base mt-3"
        onClick={handleSignUp}
      >
        {signUpProgress ? (
          <div role="status">
            <svg
              aria-hidden="true"
              className="w-6 h-6 mr-2 text-gray-200 animate-spin dark:text-gray-600 fill-blue-600"
              viewBox="0 0 100 101"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z"
                fill="currentColor"
              />
              <path
                d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z"
                fill="currentFill"
              />
            </svg>
          </div>
        ) : null}
        <p>{signUpProgress ? "Signing up..." : "Sign up"}</p>
      </button>
      {/* <div
        className="flex space-x-3 items-center justify-center w-full my-4 p-3.5 rounded-md cursor-pointer border border-neutral-200 dark:border-0 bg-white dark:bg-neutral-700 text-sm md:text-base"
        onClick={() => auth.login()}
      >
        <FcGoogle size={25} />
        <button>Sign up with Google</button>
      </div> */}
      <div className="flex space-x-2 justify-center mt-4">
        <p>Already have an account?</p>
        <Link href={uiRoutes.signIn} passHref>
          <p className="text-blue-500 font-medium cursor-pointer">Sign in</p>
        </Link>
      </div>
    </div>
  );
}
