import React, { useEffect } from "react";
import { Menu } from "@mantine/core";
import { GoKebabHorizontal } from "react-icons/go";
import { MdOutlineKeyboardArrowRight } from "react-icons/md";

export default function FileMenu({ item, onAction, actions }) {
  return (
    <Menu shadow="md" width={200} position="bottom-end" withinPortal>
      <Menu.Target>
        <button
          className="p-3 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full"
          onClick={(e) => e.stopPropagation()}
        >
          <GoKebabHorizontal className="w-4 h-4 rotate-90 text-gray-600 dark:text-gray-100" />
        </button>
      </Menu.Target>

      <Menu.Dropdown>
        {actions.map((action) => (
          <Menu.Item
            key={action.name}
            icon={
              <action.icon
                size={14}
                className={action?.action === "delete" ? "text-red-500" : ""}
              />
            }
            onClick={(e) => {
              e.stopPropagation();
              onAction(action.action, item);
            }}
          >
            {action?.subMenu && (
              <Menu position="right-start" trigger="hover" offset={20}>
                <Menu.Target>
                  <div
                    onClick={(e) => e.stopPropagation()}
                    className="flex justify-between items-center"
                  >
                    <p>{action.name}</p>
                    <MdOutlineKeyboardArrowRight className="w-4 h-4" />
                  </div>
                </Menu.Target>
                <Menu.Dropdown className="-mt-[0.6rem]">
                  {action.subMenu.map((subAction) => (
                    <Menu.Item
                      key={subAction.name}
                      onClick={(e) => {
                        e.stopPropagation();
                        onAction(subAction.action, item);
                      }}
                    >
                      <p
                        className={
                          subAction?.action === "delete" ? "text-red-500" : ""
                        }
                      >
                        {subAction.name}
                      </p>
                    </Menu.Item>
                  ))}
                </Menu.Dropdown>
              </Menu>
            )}

            {!action?.subMenu && (
              <p className={action?.action === "delete" ? "text-red-500" : ""}>
                {action.name}
              </p>
            )}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}
