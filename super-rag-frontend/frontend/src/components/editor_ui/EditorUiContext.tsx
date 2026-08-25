import { createContext, useContext } from "react";
import type React from "react";

type EditorUiScope = "node" | "inspector";

const EditorUiContext = createContext<EditorUiScope>("node");

type EditorUiProviderProps = {
  scope?: EditorUiScope;
  children: React.ReactNode;
};

export function EditorUiProvider({ scope = "node", children }: EditorUiProviderProps) {
  return <EditorUiContext.Provider value={scope}>{children}</EditorUiContext.Provider>;
}

export function useEditorScope() {
  return useContext(EditorUiContext);
}
