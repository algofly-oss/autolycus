import { IoIosArrowBack } from "react-icons/io";
import { useRouter } from "next/router";

export default function GoBack() {
  const router = useRouter();
  return (
    <div
      className="border border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 pr-2 py-1.5 mb-6 p-1 rounded-lg w-max h-max cursor-pointer"
      onClick={() => router.push("/")}
    >
      <IoIosArrowBack size={25} />
    </div>
  );
}
