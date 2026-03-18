import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getPostPriorities, updatePostPriority } from '../api/posts';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';

export default function PostPrioritiesPage() {
  const queryClient = useQueryClient();
  const { data: priorities, isLoading } = useQuery({
    queryKey: ['postPriorities'],
    queryFn: getPostPriorities,
  });

  const mutation = useMutation({
    mutationFn: ({ postNumber, priority }: { postNumber: number; priority: number }) =>
      updatePostPriority(postNumber, priority),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['postPriorities'] });
    },
  });

  return (
    <div className="max-w-2xl">
      <h1 className="mb-2 text-2xl font-bold text-slate-900">Post Priorities</h1>
      <p className="mb-6 text-sm text-slate-500">
        Global priority for each post position. These are copied to new sieges when created.
      </p>

      {isLoading ? (
        <div className="py-12 text-center text-slate-500">Loading...</div>
      ) : (
        <div className="rounded-lg border border-slate-200 bg-white">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Post</TableHead>
                <TableHead>Priority</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {priorities?.map((p) => (
                <TableRow key={p.post_number}>
                  <TableCell className="font-medium">Post {p.post_number}</TableCell>
                  <TableCell>
                    <Select
                      value={String(p.priority)}
                      onValueChange={(val) =>
                        mutation.mutate({ postNumber: p.post_number, priority: Number(val) })
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
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
