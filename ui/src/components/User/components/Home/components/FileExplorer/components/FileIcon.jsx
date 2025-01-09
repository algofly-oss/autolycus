import React from "react";
import { FiFolder, FiFile, FiFilm, FiMusic, FiImage, FiFileText } from "react-icons/fi";
import { BsFileZip } from "react-icons/bs";
import { getFileType } from "@/shared/utils/fileUtils";

export default function FileIcon({ item }) {
  if (item.is_directory) {
    return <FiFolder size={24} className="text-blue-500" />;
  }

  const fileType = getFileType(item.name);
  switch (fileType) {
    case "video":
      return <FiFilm size={24} className="text-purple-500" />;
    case "audio":
      return <FiMusic size={24} className="text-green-500" />;
    case "image":
      return <FiImage size={24} className="text-pink-500" />;
    case "document":
      return <FiFileText size={24} className="text-orange-500" />;
    case "compressed":
      return <BsFileZip size={24} className="text-purple-500" />;
    default:
      return <FiFile size={24} className="text-gray-500" />;
  }
}
