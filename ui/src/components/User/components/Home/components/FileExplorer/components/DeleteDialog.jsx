import React, { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { AiOutlineClose } from "react-icons/ai";
import { Button } from "@mantine/core";
import { useOnClickOutside } from "usehooks-ts";

export default function DeleteDialog({ open, item, onClose, onDelete }) {
  const dialogRef = useRef(null);

  useOnClickOutside(dialogRef, () => onClose());

  useEffect(() => {
    if (open && dialogRef.current) {
      dialogRef.current.focus();
    }
  }, [open]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      onDelete();
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  return (
    <>
      <motion.div

        initial={{ opacity: 0, scale: 0.75, y: -60 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0, y: -150 }}
        className="flex justify-center items-center fixed inset-0 z-50 outline-none focus:outline-none"
        onKeyDown={handleKeyDown}
      >
        <div className="relative w-auto my-6 max-w-xl mx-4">
          {/* content */}
          <div
            ref={dialogRef}
            tabIndex={0}
            className="border-0 rounded-lg shadow-lg relative flex flex-col w-full bg-white dark:bg-[#1A1B1E] outline-none focus:outline-none"
          >
            {/*header*/}
            <div className="flex items-center justify-between p-3 border-b border-zinc-200 dark:border-zinc-700 rounded-t">
              <p className="text-sm md:text-base font-medium md:mx-6">
                Confirm Delete
              </p>
              <div
                className="hover:bg-neutral-200 dark:hover:bg-zinc-700 p-1 rounded-lg cursor-pointer"
                onClick={onClose}
              >
                <AiOutlineClose size={15} />
              </div>
            </div>

            {/*body*/}
            <div className="relative px-6 py-4 flex flex-col items-start justify-center md:mx-3">
              <div className="flex w-full">
                <p className="text-sm md:text-base font-medium md:mx-6">
                  Are you sure you want to delete{" "}
                  <strong className="break-all">{item?.name}</strong>?
                  {item?.is_directory &&
                    " This will delete all contents inside the folder."}
                </p>
              </div>

              <div className="flex items-center justify-end gap-4 w-full md:mt-4">
                <Button
                  variant="default"
                  onClick={onClose}
                >
                  Cancel
                </Button>
                <Button
                  color="red"
                  className="text-red-500 hover:text-white"
                  onClick={onDelete}
                >
                  Rename
                </Button>
              </div>
            </div>
          </div>
        </div>
      </motion.div>


      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-40"
        style={{
          backgroundColor: "rgba(0, 0, 0, 0.2)",
          backdropFilter: "blur(1px)",
          WebkitBackdropFilter: "blur(1px)",
        }}
      />
    </>
  );
}
