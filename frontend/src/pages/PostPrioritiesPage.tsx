import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPostPriorities, updatePostPriority } from "../api/posts";
import { getPostConditions } from "../api/members";
import type { PostCondition } from "../api/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { cn } from "../lib/utils";

function groupByLevel(conds: PostCondition[]) {
  const groups: Record<number, PostCondition[]> = {};
  for (const c of conds) {
    if (!groups[c.stronghold_level]) groups[c.stronghold_level] = [];
    groups[c.stronghold_level].push(c);
  }
  return groups;
}

function DescriptionCell({
  postNumber,
  value,
}: {
  postNumber: number;
  value: string | null;
}) {
  const queryClient = useQueryClient();
  const [desc, setDesc] = useState(value ?? "");

  const mutation = useMutation({
    mutationFn: (description: string | null) =>
      updatePostPriority(postNumber, { description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["postPriorities"] });
    },
  });

  return (
    <Input
      value={desc}
      onChange={(e) => setDesc(e.target.value)}
      onBlur={() => {
        const newVal = desc.trim() || null;
        if (newVal !== (value ?? null)) {
          mutation.mutate(newVal);
        }
      }}
      placeholder="e.g. Near Mana Shrine 1"
      className="h-8 text-sm"
    />
  );
}

type Tab = "priorities" | "conditions";

export default function PostPrioritiesPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<Tab>("priorities");

  const { data: priorities, isLoading } = useQuery({
    queryKey: ["postPriorities"],
    queryFn: getPostPriorities,
  });

  const { data: conditions } = useQuery({
    queryKey: ["postConditions"],
    queryFn: getPostConditions,
  });

  const mutation = useMutation({
    mutationFn: ({
      postNumber,
      priority,
    }: {
      postNumber: number;
      priority: number;
    }) => updatePostPriority(postNumber, { priority }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["postPriorities"] });
    },
  });

  return (
    <div className="max-w-3xl">
      <h1 className="mb-4 text-2xl font-bold text-slate-900">Posts</h1>

      {/* Sub-tabs */}
      <div className="mb-6 flex gap-1 rounded-lg border border-slate-200 bg-slate-100 p-1">
        <button
          className={cn(
            "flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors",
            activeTab === "priorities"
              ? "bg-white text-slate-900 shadow-sm"
              : "text-slate-600 hover:text-slate-900"
          )}
          onClick={() => setActiveTab("priorities")}
        >
          Priorities
        </button>
        <button
          className={cn(
            "flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors",
            activeTab === "conditions"
              ? "bg-white text-slate-900 shadow-sm"
              : "text-slate-600 hover:text-slate-900"
          )}
          onClick={() => setActiveTab("conditions")}
        >
          Conditions
        </button>
      </div>

      {/* Priorities tab */}
      {activeTab === "priorities" && (
        <>
          <p className="mb-4 text-sm text-slate-500">
            Global priority and description for each post. Copied to new sieges
            when created.
          </p>
          {isLoading ? (
            <div className="py-12 text-center text-slate-500">Loading...</div>
          ) : (
            <div className="rounded-lg border border-slate-200 bg-white">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-24">Post</TableHead>
                    <TableHead className="w-36">Priority</TableHead>
                    <TableHead>Description</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {priorities?.map((p) => (
                    <TableRow key={p.post_number}>
                      <TableCell className="font-medium">
                        Post {p.post_number}
                      </TableCell>
                      <TableCell>
                        <Select
                          value={String(p.priority)}
                          onValueChange={(val) =>
                            mutation.mutate({
                              postNumber: p.post_number,
                              priority: Number(val),
                            })
                          }
                        >
                          <SelectTrigger className="w-32">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="1">Low</SelectItem>
                            <SelectItem value="2">Medium</SelectItem>
                            <SelectItem value="3">High</SelectItem>
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell>
                        <DescriptionCell
                          postNumber={p.post_number}
                          value={p.description}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </>
      )}

      {/* Conditions tab */}
      {activeTab === "conditions" && (
        <>
          <p className="mb-4 text-sm text-slate-500">
            Reference list of all post conditions by stronghold level.
          </p>
          {conditions ? (
            <div className="space-y-4">
              {Object.entries(groupByLevel(conditions))
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([level, conds]) => (
                  <div
                    key={level}
                    className="rounded-lg border border-slate-200 bg-white p-4"
                  >
                    <h3 className="mb-3 text-sm font-semibold text-slate-900">
                      Stronghold Level {level}
                      <Badge variant="secondary" className="ml-2">
                        {conds.length}
                      </Badge>
                    </h3>
                    <ul className="space-y-1.5">
                      {conds.map((c) => (
                        <li key={c.id} className="text-sm text-slate-700">
                          {c.description}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
            </div>
          ) : (
            <div className="py-12 text-center text-slate-500">Loading...</div>
          )}
        </>
      )}
    </div>
  );
}
