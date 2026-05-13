"use client";

import { ReactNode } from "react";
import { motion } from "motion/react";

interface DataPanelProps {
  title: string;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function DataPanel({ title, eyebrow, action, children, className = "" }: DataPanelProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.42, ease: "easeOut" }}
      className={`premium-panel ${className}`}
    >
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          {eyebrow ? <p className="panel-eyebrow">{eyebrow}</p> : null}
          <h2 className="panel-title">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </motion.section>
  );
}

