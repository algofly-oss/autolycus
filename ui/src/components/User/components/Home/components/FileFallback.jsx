import { FiFile } from "react-icons/fi";

export default function FileFallback() {
  return (
    <div className="absolute inset-0 flex items-center justify-center bg-neutral-200 text-neutral-500 dark:bg-neutral-900 dark:text-neutral-500">
      <FiFile className="h-7 w-7" aria-hidden="true" />
    </div>
  );
}
