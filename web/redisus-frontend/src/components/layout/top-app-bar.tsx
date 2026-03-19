"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type TopAppBarProps = {
  userName: string;
  userRole?: string;
  userEmail?: string;
  userPhotoUrl?: string;
};

export function TopAppBar({
  userName,
  userRole = "Profissional de Saúde",
  userPhotoUrl,
}: TopAppBarProps) {
  const router = useRouter();
  const [isHovered, setIsHovered] = useState(false);

  const handleSearchClick = () => {
    router.push("/ai-search");
  };

  return (
    <header className="fixed top-0 right-0 left-64 h-16 z-40 bg-surface-container-lowest/80 backdrop-blur-xl flex items-center px-8 border-b border-outline-variant/10 font-nav">
      {/* Spacer */}
      <div className="flex-1" />

      {/* Search Bar - Navigates to AI Search (Centered) */}
      <button
        onClick={handleSearchClick}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className="flex items-center bg-surface-container-low rounded-full px-4 py-2.5 w-96 group hover:bg-surface-container hover:ring-2 hover:ring-primary/30 transition-all cursor-pointer text-left"
      >
        <span
          className={`material-symbols-outlined text-lg mr-2 transition-all duration-300 ${
            isHovered ? "text-primary" : "text-outline"
          }`}
        >
          {isHovered ? "auto_awesome" : "search"}
        </span>
        <span className="text-sm text-on-surface-variant group-hover:text-on-surface transition-colors">
          {isHovered
            ? "Buscar com IA..."
            : "Buscar pacientes ou relatórios..."}
        </span>
      </button>

      {/* Right Section */}
      <div className="flex-1 flex items-center justify-end gap-6">
        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button className="hover:bg-surface-container rounded-full p-2 transition-all relative">
            <span className="material-symbols-outlined text-on-surface-variant">
              notifications
            </span>
            <span className="absolute top-2 right-2 w-2 h-2 bg-error rounded-full"></span>
          </button>
          <button className="hover:bg-surface-container rounded-full p-2 transition-all">
            <span className="material-symbols-outlined text-on-surface-variant">
              help_outline
            </span>
          </button>
        </div>

        {/* Divider */}
        <div className="h-8 w-[1px] bg-outline-variant/30"></div>

        {/* User Profile */}
        <div className="flex items-center gap-3 cursor-pointer hover:opacity-80 transition-opacity">
          <div className="text-right">
            <p className="text-sm font-bold text-on-surface leading-none">
              {userName}
            </p>
            <p className="text-[10px] text-primary font-medium uppercase tracking-wider mt-1">
              {userRole}
            </p>
          </div>
          {userPhotoUrl ? (
            <img
              src={userPhotoUrl}
              alt={`${userName} Profile Picture`}
              className="w-10 h-10 rounded-full border-2 border-outline-variant/20 object-cover"
            />
          ) : (
            <div className="w-10 h-10 rounded-full border-2 border-outline-variant/20 bg-surface-container flex items-center justify-center">
              <span className="material-symbols-outlined text-on-surface-variant">
                person
              </span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
