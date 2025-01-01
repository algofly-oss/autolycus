import apiRoutes from '@/shared/routes/apiRoutes';
import axios from 'axios';
import React, { useEffect, useState } from 'react';
import { FiFolder, FiFile, FiArrowLeft, FiLoader, FiFilm, FiMusic, FiImage, FiFileText } from 'react-icons/fi';
import { getFileType } from '@/shared/utils/fileUtils';

export default function FileExplorer({ initialPath, onPathChange }) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError('');
      if (initialPath) {
        try {
          console.log("initialPath", initialPath);
          const encodedPath = encodeURIComponent(initialPath.replace(/^\/downloads\/*/, ''));
          const response = await axios.get(`${apiRoutes.browseFiles}?path=${encodedPath}`);
          setItems(response.data);
        } catch (err) {
          setError(err.message);
        } finally {
          setLoading(false);
        }
      }
    };

    fetchData();
  }, [initialPath]);

  function handleItemClick(item) {
    if (item.is_directory) {
      onPathChange(`${initialPath}/${item.name}`);
    } else {
      // Handle file click if needed
      alert(`Clicked file: ${item.name}`);
    }
  }

  function handleGoBack() {
    if (!initialPath.includes('/')) return;
    const newPath = initialPath.substring(0, initialPath.lastIndexOf('/'));
    onPathChange(newPath || '/downloads');
  }

  // Get appropriate icon based on file type
  function getFileIcon(item) {
    if (item.is_directory) {
      return <FiFolder size={24} className="text-blue-500" />;
    }

    const fileType = getFileType(item.name);
    switch (fileType) {
      case 'video':
        return <FiFilm size={24} className="text-purple-500" />;
      case 'audio':
        return <FiMusic size={24} className="text-green-500" />;
      case 'image':
        return <FiImage size={24} className="text-pink-500" />;
      case 'document':
        return <FiFileText size={24} className="text-orange-500" />;
      default:
        return <FiFile size={24} className="text-gray-500" />;
    }
  }

  // Create breadcrumb items from the path, excluding /downloads/{id}
  const pathParts = initialPath.split('/').filter(Boolean);
  // Find the index after "downloads" to start showing breadcrumbs
  const startIndex = pathParts.findIndex(part => part === 'downloads') + 1;
  const visibleParts = pathParts.slice(startIndex);
  const breadcrumbs = visibleParts.map((part, index) => {
    // Reconstruct the full path for navigation while showing only the visible part
    const fullPath = '/' + pathParts.slice(0, startIndex + index + 1).join('/');
    return { name: part, path: fullPath };
  });

  return (
    <div className="mt-6">
      {/* Navigation header */}
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={handleGoBack}
          className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-full transition-colors"
          title="Go back"
        >
          <FiArrowLeft size={20} />
        </button>

        {/* Path breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 overflow-x-auto">
          <span>/</span>
          {breadcrumbs.map((crumb, index) => (
            <React.Fragment key={crumb.path}>
              {index === 0 ? '' : <span>/</span>}
              <span
                className="hover:text-blue-500 cursor-pointer whitespace-nowrap"
                onClick={() => onPathChange(crumb.path)}
              >
                {crumb.name}
              </span>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Loading and Error states */}
      {loading && (
        <div className="flex items-center justify-center p-8">
          <FiLoader className='animate-spin w-8 h-8' />
        </div>
      )}
      {error && (
        <div className="text-red-500 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
          {error}
        </div>
      )}

      {/* File/Folder Grid */}
      <div className="flex flex-col gap-4">
        {items.map((item) => (
          <div
            key={item.name}
            onClick={() => handleItemClick(item)}
            className="p-4 rounded-lg border dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
          >
            <div className="flex items-center gap-3">
              {getFileIcon(item)}
              <div className="truncate flex w-full justify-between">
                <div className="font-medium">{item.name}</div>
                {!item.is_directory && (
                  <div className="text-sm text-gray-500">
                    {(item.size / 1024 / 1024).toFixed(2)} MB
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Empty state */}
      {!loading && !error && items.length === 0 && (
        <div className="text-center p-8 text-gray-500">
          This folder is empty
        </div>
      )}
    </div>
  );
}
