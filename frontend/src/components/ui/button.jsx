import * as React from "react";

export function Button({
  className = "",
  variant = "default",
  size = "default",
  type = "button",
  ...props
}) {
  const baseStyles =
    "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 cursor-pointer";

  const variants = {
    default:
      "bg-blue-600 text-white shadow hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-700",
    destructive:
      "bg-red-600 text-white shadow-sm hover:bg-red-700 dark:bg-red-900 dark:hover:bg-red-800",
    outline:
      "border border-zinc-300 dark:border-zinc-700 bg-transparent shadow-sm hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-900 dark:text-zinc-100",
    secondary:
      "bg-zinc-100 text-zinc-900 shadow-sm hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
    ghost:
      "hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100",
    link: "text-blue-600 underline-offset-4 hover:underline dark:text-blue-400",
  };

  const sizes = {
    default: "h-9 px-4 py-2",
    sm: "h-8 rounded-md px-3 text-xs",
    lg: "h-10 rounded-md px-8",
    icon: "h-9 w-9",
  };

  const variantClass = variants[variant] || variants.default;
  const sizeClass = sizes[size] || sizes.default;

  return (
    <button
      type={type}
      className={`${baseStyles} ${variantClass} ${sizeClass} ${className}`}
      {...props}
    />
  );
}
