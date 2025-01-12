import React, { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { AiOutlineClose } from "react-icons/ai";
import { Button } from "@mantine/core";

export default function RenameDialog({ open, item, onClose, onRename }) {
  const [newName, setNewName] = useState("");
  const renameInput = useRef(null);

  useEffect(() => {
    if (item) {
      if (item.is_directory) {
        setNewName(item.name);
      } else {
        const baseName = item.name.split(".").slice(0, -1).join(".");
        setNewName(baseName);
      }
    }
  }, [item]);

  useEffect(() => {
    if (open && renameInput.current) {
      renameInput.current.focus();
    }
  }, [open]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        onClose();
      }
      if (e.key === "Enter" && document.activeElement === renameInput.current) {
        handleRename();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [newName, item]);

  const handleRename = () => {
    if (item.is_directory) {
      onRename(newName);
    } else {
      const extension = item.name.split(".").pop();
      onRename(`${newName}.${extension}`);
    }
  };

  return (
    <>
      <motion.div
        initial={{ opacity: 0, scale: 0.75, y: -60 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{
          type: "spring",
          duration: 0.5,
          bounce: 0.3,
        }}
        exit={{ opacity: 0, scale: 0, y: -150 }}
        className="flex justify-center items-center fixed inset-0 z-50 outline-none focus:outline-none"
      >
        <div className="relative w-auto my-6 max-w-xl mx-4">
          <div
            tabIndex={0}
            className="border dark:border-neutral-800 rounded-lg shadow-lg relative flex flex-col w-full bg-white dark:bg-[#1A1B1E] outline-none focus:outline-none"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-3 border-b border-zinc-200 dark:border-zinc-700 rounded-t">
              <p className="text-sm md:text-base font-medium md:mx-6">
                Rename Item
              </p>
              <div
                className="hover:bg-neutral-200 dark:hover:bg-zinc-700 p-1 rounded-lg cursor-pointer"
                onClick={onClose}
              >
                <AiOutlineClose size={15} />
              </div>
            </div>

            {/* Body */}
            <div className="relative px-6 py-4 flex flex-col items-start justify-center md:mx-3">
              <div className="flex w-full">
                <input
                  ref={renameInput}
                  type="text"
                  value={newName}
                  placeholder="Enter new name"
                  className={`text-xs md:text-sm border-0 outline-0 focus:ring-0 w-full bg-zinc-100 dark:bg-black pl-4 md:w-80 ${
                    item.is_directory ? "rounded-lg" : "rounded-l-lg"
                  }`}
                  onChange={(e) => setNewName(e.target.value)}
                />
                {!item.is_directory && (
                  <input
                    type="text"
                    value={`.${item.name.split(".").pop()}`}
                    disabled
                    className="text-xs md:text-sm border-0 outline-0 focus:ring-0 rounded-r-lg bg-zinc-300 dark:bg-black/30 pl-2- w-20"
                  />
                )}
              </div>

              <div className="flex items-center justify-end gap-4 w-full md:mt-4">
                <Button variant="default" onClick={onClose}>
                  Cancel
                </Button>
                <Button
                  color="Blue"
                  className="text-blue-500 hover:text-white"
                  onClick={handleRename}
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
