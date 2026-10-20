import {
  Component,
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { QueryClient, useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { ApiError } from "../api/real";
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, staleTime: 20000, refetchOnWindowFocus: false },
  },
});
export function useSession() {
  return useQuery({
    queryKey: ["session"],
    queryFn: api.session,
    retry: false,
  });
}
export function usePolicies() {
  return useQuery({ queryKey: ["policies"], queryFn: api.policies });
}
const Selection = createContext<{
  selected: string;
  select: (id: string) => void;
}>({ selected: "", select: () => {} });
export function SelectionProvider({ children }: { children: ReactNode }) {
  const [selected, select] = useState("");
  useEffect(() => {
    const clear = () => select("");
    window.addEventListener("policyiq:clear", clear);
    return () => window.removeEventListener("policyiq:clear", clear);
  }, []);
  return (
    <Selection.Provider value={{ selected, select }}>
      {children}
    </Selection.Provider>
  );
}
export const useSelection = () => useContext(Selection);
export function message(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
}
export function isUnauthorized(error: unknown) {
  return error instanceof ApiError && error.status === 401;
}
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div className="fatal">
        <h1>This page could not be displayed.</h1>
        <p>Your saved documents are still on the server.</p>
        <button onClick={() => window.location.reload()}>Reload the app</button>
      </div>
    ) : (
      this.props.children
    );
  }
}
