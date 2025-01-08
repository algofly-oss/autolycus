import React from "react";
import { Menu } from "@mantine/core";
import { GoKebabHorizontal } from "react-icons/go";
import { FiCopy, FiMove, FiTrash2, FiDownload } from "react-icons/fi";
import { FaRegFileArchive } from "react-icons/fa";

export default function FileMenu({ item, onAction }) {
  const actions = [
    { name: "Copy", icon: FiCopy, action: "copy" },
    { name: "Move", icon: FiMove, action: "move" },
    { name: "Delete", icon: FiTrash2, action: "delete" },
    ...(item.is_directory ? [{ name: "Archive", icon: FaRegFileArchive, action: "archive" }] : [{ name: "Download", icon: FiDownload, action: "download" }])
  ];

  return (
    <Menu shadow="md" width={200} position="bottom-end" withinPortal>
      <Menu.Target>
        <button
          className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full"
          onClick={(e) => e.stopPropagation()}
        >
          <GoKebabHorizontal className="w-4 h-4 rotate-90" />
        </button>
      </Menu.Target>

      <Menu.Dropdown>
        {actions.map((action) => (
          <Menu.Item
            key={action.name}
            icon={<action.icon size={14} />}
            onClick={(e) => {
              e.stopPropagation();
              onAction(action.action, item);
            }}
          >
            {action.name}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}
