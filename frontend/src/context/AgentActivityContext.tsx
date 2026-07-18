import React, { createContext, useCallback, useContext, useState } from 'react';

interface AgentActivityContextValue {
  isActive: boolean;
  label: string;
  /** Wrap an async call so the navbar reflects real in-flight work instead of a hardcoded status. */
  withActivity: <T>(label: string, task: () => Promise<T>) => Promise<T>;
}

const AgentActivityContext = createContext<AgentActivityContextValue | undefined>(undefined);

export const AgentActivityProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeCount, setActiveCount] = useState(0);
  const [label, setLabel] = useState('Idle');

  const withActivity = useCallback(async <T,>(taskLabel: string, task: () => Promise<T>): Promise<T> => {
    setLabel(taskLabel);
    setActiveCount((c) => c + 1);
    try {
      return await task();
    } finally {
      setActiveCount((c) => Math.max(0, c - 1));
    }
  }, []);

  return (
    <AgentActivityContext.Provider value={{ isActive: activeCount > 0, label, withActivity }}>
      {children}
    </AgentActivityContext.Provider>
  );
};

export function useAgentActivity(): AgentActivityContextValue {
  const ctx = useContext(AgentActivityContext);
  if (!ctx) {
    throw new Error('useAgentActivity must be used within an AgentActivityProvider');
  }
  return ctx;
}
