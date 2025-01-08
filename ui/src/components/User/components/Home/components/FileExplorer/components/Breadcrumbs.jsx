import React from "react";

export default function Breadcrumbs({ initialPath, onPathChange }) {
  const pathParts = initialPath.split("/").filter(Boolean);
  const startIndex = pathParts.findIndex((part) => part === "downloads") + 3;
  const visibleParts = pathParts.slice(startIndex);
  const rootPath = "/" + pathParts.slice(0, startIndex).join("/");
  const breadcrumbs = [{ name: "home", path: rootPath }, ...visibleParts.map((part, index) => {
    const fullPath = "/" + pathParts.slice(0, startIndex + index + 1).join("/");
    return { name: part, path: fullPath };
  })];

  return (
    <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 overflow-x-auto no-scrollbar">
      <span>/</span>
      {breadcrumbs.map((crumb, index) => (
        <React.Fragment key={crumb.path}>
          {index === 0 ? "" : <span>/</span>}
          <span
            className="hover:text-blue-500 cursor-pointer whitespace-nowrap"
            onClick={() => onPathChange(crumb.path)}
          >
            {crumb.name}
          </span>
        </React.Fragment>
      ))}
      <div
        ref={(el) =>
          el &&
          el.scrollIntoView({
            behavior: "smooth",
            block: "end",
            inline: "end",
          })
        }
      ></div>
    </div>
  );
}
