import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getSiege,
  updateSiege,
  deleteSiege,
  activateSiege,
  completeSiege,
  cloneSiege,
  validateSiege,
  getBuildings,
  createBuilding,
  updateBuilding,
  deleteBuilding,
  getBuildingTypes,
} from '../api/sieges';
import {
  notifySiegeMembers,
  getNotificationBatch,
  postToChannel,
  generateImages,
} from '../api/notifications';
import type {
  BuildingType,
  ValidationResult,
  NotifyResponse,
  NotificationResultItem,
} from '../api/types';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '../components/ui/dialog';
import { Badge } from '../components/ui/badge';
import {
  ArrowLeft,
  Trash2,
  LayoutGrid,
  MessageSquare,
  Users,
  GitCompare,
  Settings,
  Check,
  X,
  Loader2,
  AlertCircle,
  Download,
  Send,
  Image,
} from 'lucide-react';
import { isAxiosError } from 'axios';
import { cn } from '../lib/utils';

export default function SiegeSettingsPage() {
  const { id } = useParams<{ id: string }>();
  const siegeId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [date, setDate] = useState('');
  const [scrollCount, setScrollCount] = useState('3');
  const [settingsError, setSettingsError] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteBuildingId, setDeleteBuildingId] = useState<number | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [activateErrors, setActivateErrors] = useState<string[]>([]);
  const [newBuildingType, setNewBuildingType] = useState<BuildingType>('stronghold');
  const [newBuildingNum, setNewBuildingNum] = useState('1');

  // Notification state
  const [notifyConfirmOpen, setNotifyConfirmOpen] = useState(false);
  const [postConfirmOpen, setPostConfirmOpen] = useState(false);
  const [notifyBatch, setNotifyBatch] = useState<NotifyResponse | null>(null);
  const [postChannelResult, setPostChannelResult] = useState<string | null>(null);
  const [postChannelError, setPostChannelError] = useState<string | null>(null);
  const [generatedImages, setGeneratedImages] = useState<{
    assignments_image: string;
    reserves_image: string;
  } | null>(null);

  const { data: siege, isLoading: siegeLoading } = useQuery({
    queryKey: ['siege', siegeId],
    queryFn: () => getSiege(siegeId),
  });

  const { data: buildings } = useQuery({
    queryKey: ['buildings', siegeId],
    queryFn: () => getBuildings(siegeId),
  });

  const { data: buildingTypes } = useQuery({
    queryKey: ['buildingTypes'],
    queryFn: getBuildingTypes,
  });

  // Notification batch polling — runs until all results have success !== null or status === "completed"
  const batchDone = (results: NotificationResultItem[], status: string) =>
    status === 'completed' || results.every((r) => r.success !== null);

  const { data: batchData } = useQuery({
    queryKey: ['notificationBatch', siegeId, notifyBatch?.batch_id],
    queryFn: () => getNotificationBatch(siegeId, notifyBatch!.batch_id),
    enabled: notifyBatch != null,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 3000;
      return batchDone(data.results, data.status) ? false : 3000;
    },
  });

  useEffect(() => {
    if (siege) {
      setDate(siege.date ?? '');
      setScrollCount(String(siege.defense_scroll_count));
    }
  }, [siege]);

  const updateMutation = useMutation({
    mutationFn: () =>
      updateSiege(siegeId, {
        date: date || null,
        defense_scroll_count: Number(scrollCount),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['siege', siegeId] });
      queryClient.invalidateQueries({ queryKey: ['sieges'] });
      setSettingsError('');
    },
    onError: (err) => {
      setSettingsError(isAxiosError(err) ? (err.response?.data?.detail ?? 'Save failed') : 'Save failed');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteSiege(siegeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sieges'] });
      navigate('/sieges');
    },
  });

  const activateMutation = useMutation({
    mutationFn: () => activateSiege(siegeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['siege', siegeId] });
      queryClient.invalidateQueries({ queryKey: ['sieges'] });
      setActivateErrors([]);
    },
    onError: (err) => {
      if (isAxiosError(err) && err.response?.status === 400) {
        const data = err.response.data as { errors?: string[] };
        setActivateErrors(data.errors ?? ['Activation failed']);
      } else {
        setActivateErrors(['Activation failed']);
      }
    },
  });

  const completeMutation = useMutation({
    mutationFn: () => completeSiege(siegeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['siege', siegeId] });
      queryClient.invalidateQueries({ queryKey: ['sieges'] });
    },
  });

  const cloneMutation = useMutation({
    mutationFn: () => cloneSiege(siegeId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['sieges'] });
      navigate(`/sieges/${data.id}`);
    },
  });

  const validateMutation = useMutation({
    mutationFn: () => validateSiege(siegeId),
    onSuccess: (data) => setValidation(data),
  });

  const addBuildingMutation = useMutation({
    mutationFn: () =>
      createBuilding(siegeId, {
        building_type: newBuildingType,
        building_number: Number(newBuildingNum),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['buildings', siegeId] });
    },
  });

  const updateBuildingMutation = useMutation({
    mutationFn: ({
      buildingId,
      data,
    }: {
      buildingId: number;
      data: { level?: number; is_broken?: boolean };
    }) => updateBuilding(siegeId, buildingId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['buildings', siegeId] });
    },
  });

  const deleteBuildingMutation = useMutation({
    mutationFn: (buildingId: number) => deleteBuilding(siegeId, buildingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['buildings', siegeId] });
      setDeleteBuildingId(null);
    },
  });

  const notifyMutation = useMutation({
    mutationFn: () => notifySiegeMembers(siegeId),
    onSuccess: (data) => {
      setNotifyBatch(data);
      setNotifyConfirmOpen(false);
    },
  });

  const postChannelMutation = useMutation({
    mutationFn: () => postToChannel(siegeId),
    onSuccess: (data) => {
      setPostChannelResult(data.status === 'ok' ? 'Posted successfully.' : (data.detail ?? 'Posted.'));
      setPostChannelError(null);
      setPostConfirmOpen(false);
    },
    onError: (err) => {
      setPostChannelError(
        isAxiosError(err) ? (err.response?.data?.detail ?? 'Post failed') : 'Post failed',
      );
      setPostChannelResult(null);
      setPostConfirmOpen(false);
    },
  });

  const generateImagesMutation = useMutation({
    mutationFn: () => generateImages(siegeId),
    onSuccess: (data) => setGeneratedImages(data),
  });

  function downloadImage(base64: string, filename: string) {
    const byteString = atob(base64);
    const ab = new ArrayBuffer(byteString.length);
    const ia = new Uint8Array(ab);
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i);
    }
    const blob = new Blob([ab], { type: 'image/png' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (siegeLoading) {
    return <div className="py-12 text-center text-slate-500">Loading...</div>;
  }

  return (
    <div className="max-w-3xl">
      <Link
        to="/sieges"
        className="mb-6 flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Sieges
      </Link>

      <div className="mb-6 flex items-start justify-between">
        <h1 className="text-2xl font-bold text-slate-900">
          Siege {siege?.date ?? `#${siegeId}`}
        </h1>
        <div className="flex gap-2 text-sm">
          <Link
            to={`/sieges/${siegeId}/board`}
            className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-slate-700 hover:bg-slate-50"
          >
            <LayoutGrid className="h-4 w-4" />
            Board
          </Link>
          <Link
            to={`/sieges/${siegeId}/posts`}
            className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-slate-700 hover:bg-slate-50"
          >
            <MessageSquare className="h-4 w-4" />
            Posts
          </Link>
          <Link
            to={`/sieges/${siegeId}/members`}
            className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-slate-700 hover:bg-slate-50"
          >
            <Users className="h-4 w-4" />
            Members
          </Link>
          <Link
            to={`/sieges/${siegeId}/compare`}
            className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-slate-700 hover:bg-slate-50"
          >
            <GitCompare className="h-4 w-4" />
            Compare
          </Link>
          <span className="flex items-center gap-1 rounded-md border border-slate-300 bg-slate-100 px-3 py-1.5 text-slate-700 font-medium">
            <Settings className="h-4 w-4" />
            Settings
          </span>
        </div>
      </div>

      {/* Settings */}
      <section className="mb-6 rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-base font-semibold text-slate-900">Siege Settings</h2>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="date">Date</Label>
            <Input
              id="date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="scrolls">Defense Scroll Count</Label>
            <Input
              id="scrolls"
              type="number"
              min="0"
              value={scrollCount}
              onChange={(e) => setScrollCount(e.target.value)}
            />
          </div>
          {settingsError && <p className="text-sm text-red-600">{settingsError}</p>}
          <Button onClick={() => updateMutation.mutate()} disabled={updateMutation.isPending}>
            {updateMutation.isPending ? 'Saving...' : 'Save Settings'}
          </Button>
          {updateMutation.isSuccess && (
            <span className="ml-3 text-sm text-green-600">Saved.</span>
          )}
        </div>
      </section>

      {/* Buildings */}
      <section className="mb-6 rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-base font-semibold text-slate-900">Buildings</h2>

        {buildings && buildings.length > 0 && (
          <div className="mb-4 space-y-2">
            {buildings.map((b) => (
              <div
                key={b.id}
                className="flex items-center gap-3 rounded-md border border-slate-100 bg-slate-50 px-3 py-2"
              >
                <span className="w-32 text-sm font-medium capitalize">
                  {b.building_type.replace(/_/g, ' ')} {b.building_number}
                </span>
                <div className="flex items-center gap-1.5">
                  <Label htmlFor={`lvl-${b.id}`} className="text-xs text-slate-500">
                    Lvl
                  </Label>
                  <Input
                    id={`lvl-${b.id}`}
                    type="number"
                    min="1"
                    max="10"
                    className="h-7 w-16 text-xs"
                    defaultValue={b.level}
                    onBlur={(e) => {
                      const val = Number(e.target.value);
                      if (val !== b.level) {
                        updateBuildingMutation.mutate({
                          buildingId: b.id,
                          data: { level: val },
                        });
                      }
                    }}
                  />
                </div>
                <div className="flex items-center gap-1.5">
                  <Checkbox
                    id={`broken-${b.id}`}
                    checked={b.is_broken}
                    onCheckedChange={(v) =>
                      updateBuildingMutation.mutate({
                        buildingId: b.id,
                        data: { is_broken: Boolean(v) },
                      })
                    }
                  />
                  <Label htmlFor={`broken-${b.id}`} className="text-xs text-slate-500">
                    Broken
                  </Label>
                </div>
                <button
                  className="ml-auto text-red-500 hover:text-red-700"
                  onClick={() => setDeleteBuildingId(b.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-end gap-3">
          <div className="space-y-1.5">
            <Label>Type</Label>
            <Select
              value={newBuildingType}
              onValueChange={(v) => setNewBuildingType(v as BuildingType)}
            >
              <SelectTrigger className="w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {buildingTypes?.map((bt) => (
                  <SelectItem key={bt.value} value={bt.value}>
                    {bt.display}
                  </SelectItem>
                )) ?? (
                  <>
                    <SelectItem value="stronghold">Stronghold</SelectItem>
                    <SelectItem value="mana_shrine">Mana Shrine</SelectItem>
                    <SelectItem value="magic_tower">Magic Tower</SelectItem>
                    <SelectItem value="defense_tower">Defense Tower</SelectItem>
                    <SelectItem value="post">Post</SelectItem>
                  </>
                )}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Number</Label>
            <Input
              type="number"
              min="1"
              className="w-20"
              value={newBuildingNum}
              onChange={(e) => setNewBuildingNum(e.target.value)}
            />
          </div>
          <Button
            onClick={() => addBuildingMutation.mutate()}
            disabled={addBuildingMutation.isPending}
          >
            Add Building
          </Button>
        </div>
      </section>

      {/* Lifecycle */}
      <section className="mb-6 rounded-lg border border-slate-200 bg-white p-6">
        <div className="mb-4 flex items-center gap-3">
          <h2 className="text-base font-semibold text-slate-900">Lifecycle</h2>
          {siege?.status === 'planning' && (
            <Badge variant="secondary">Planning</Badge>
          )}
          {siege?.status === 'active' && (
            <Badge className="bg-green-100 text-green-800 hover:bg-green-100">Active</Badge>
          )}
          {siege?.status === 'complete' && (
            <Badge variant="outline">Complete</Badge>
          )}
        </div>
        <div className="flex flex-wrap gap-3">
          {siege?.status === 'planning' && (
            <Button
              variant="default"
              onClick={() => activateMutation.mutate()}
              disabled={activateMutation.isPending}
            >
              Start Siege
            </Button>
          )}
          {siege?.status === 'active' && (
            <Button
              variant="secondary"
              onClick={() => completeMutation.mutate()}
              disabled={completeMutation.isPending}
            >
              Close Siege
            </Button>
          )}
          <Button
            variant="outline"
            onClick={() => cloneMutation.mutate()}
            disabled={cloneMutation.isPending}
          >
            Clone
          </Button>
          {siege?.status === 'planning' && (
            <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
              Delete
            </Button>
          )}
        </div>
        {activateErrors.length > 0 && (
          <div className="mt-4 space-y-1 rounded-md bg-red-50 p-3">
            {activateErrors.map((e, i) => (
              <p key={i} className="text-sm text-red-700">
                {e}
              </p>
            ))}
          </div>
        )}
      </section>

      {/* Validation */}
      <section className="mb-6 rounded-lg border border-slate-200 bg-white p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-900">Validation</h2>
          <Button
            variant="outline"
            size="sm"
            onClick={() => validateMutation.mutate()}
            disabled={validateMutation.isPending}
          >
            {validateMutation.isPending ? 'Checking...' : 'Run Validation'}
          </Button>
        </div>
        {validation && (
          <div className="space-y-2">
            {validation.errors.length === 0 && validation.warnings.length === 0 && (
              <p className="text-sm text-green-600">No issues found.</p>
            )}
            {validation.errors.map((e, i) => (
              <div key={i} className="flex items-start gap-2 rounded-md bg-red-50 px-3 py-2">
                <Badge variant="destructive" className="mt-0.5 shrink-0">
                  Error {e.rule}
                </Badge>
                <p className="text-sm text-red-700">{e.message}</p>
              </div>
            ))}
            {validation.warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-2 rounded-md bg-yellow-50 px-3 py-2">
                <Badge variant="yellow" className="mt-0.5 shrink-0">
                  Warning {w.rule}
                </Badge>
                <p className="text-sm text-yellow-800">{w.message}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Discord Notifications */}
      <section className="mb-6 rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-base font-semibold text-slate-900">Discord Notifications</h2>

        <div className="space-y-6">
          {/* Notify Members */}
          <div>
            <div className="mb-2 flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setNotifyConfirmOpen(true)}
                disabled={notifyMutation.isPending}
              >
                <Send className="mr-1.5 h-4 w-4" />
                Notify Members
              </Button>
              {notifyMutation.isPending && (
                <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
              )}
            </div>
            {notifyBatch && (
              <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3">
                <p className="mb-2 text-xs text-slate-500">
                  Batch #{notifyBatch.batch_id} &bull; {notifyBatch.member_count} members &bull;{' '}
                  <span
                    className={cn(
                      'font-medium',
                      batchData?.status === 'completed'
                        ? 'text-green-600'
                        : 'text-amber-600',
                    )}
                  >
                    {batchData?.status ?? notifyBatch.status}
                  </span>
                </p>
                <ul className="space-y-1">
                  {(batchData?.results ?? []).map((item) => (
                    <li key={item.member_id} className="flex items-center gap-2 text-sm">
                      {item.success === true && (
                        <Check className="h-4 w-4 shrink-0 text-green-600" />
                      )}
                      {item.success === false && (
                        <X className="h-4 w-4 shrink-0 text-red-600" />
                      )}
                      {item.discord_username === null && item.success === null && (
                        <AlertCircle className="h-4 w-4 shrink-0 text-yellow-500" />
                      )}
                      {item.discord_username !== null && item.success === null && (
                        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-slate-400" />
                      )}
                      <span
                        className={cn(
                          item.success === true && 'text-slate-700',
                          item.success === false && 'text-red-700',
                          item.discord_username === null && item.success === null && 'text-yellow-700',
                          item.discord_username !== null && item.success === null && 'text-slate-500',
                        )}
                      >
                        {item.member_name}
                        {item.discord_username === null && item.success === null
                          ? ' — No Discord username'
                          : null}
                        {item.success === false && item.error
                          ? ` — ${item.error}`
                          : null}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Post to Discord */}
          <div>
            <div className="mb-2 flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPostConfirmOpen(true)}
                disabled={postChannelMutation.isPending}
              >
                <MessageSquare className="mr-1.5 h-4 w-4" />
                Post to Discord
              </Button>
              {postChannelMutation.isPending && (
                <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
              )}
            </div>
            {postChannelResult && (
              <p className="mt-1 text-sm text-green-600">{postChannelResult}</p>
            )}
            {postChannelError && (
              <p className="mt-1 text-sm text-red-600">{postChannelError}</p>
            )}
          </div>

          {/* Generate Images */}
          <div>
            <div className="mb-2 flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => generateImagesMutation.mutate()}
                disabled={generateImagesMutation.isPending}
              >
                <Image className="mr-1.5 h-4 w-4" />
                Generate Images
              </Button>
              {generateImagesMutation.isPending && (
                <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
              )}
              {generateImagesMutation.isError && (
                <span className="text-sm text-red-600">
                  {isAxiosError(generateImagesMutation.error)
                    ? (generateImagesMutation.error.response?.data?.detail ?? 'Generation failed')
                    : 'Generation failed'}
                </span>
              )}
            </div>
            {generatedImages && (
              <div className="mt-3 space-y-4">
                <div>
                  <div className="mb-1.5 flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-700">Assignments</span>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-6 px-2 text-xs"
                      onClick={() =>
                        downloadImage(
                          generatedImages.assignments_image,
                          `siege-${siegeId}-assignments.png`,
                        )
                      }
                    >
                      <Download className="mr-1 h-3 w-3" />
                      Download
                    </Button>
                  </div>
                  <img
                    src={`data:image/png;base64,${generatedImages.assignments_image}`}
                    alt="Assignments"
                    className="max-w-full rounded-md border border-slate-200"
                  />
                </div>
                <div>
                  <div className="mb-1.5 flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-700">Reserves</span>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-6 px-2 text-xs"
                      onClick={() =>
                        downloadImage(
                          generatedImages.reserves_image,
                          `siege-${siegeId}-reserves.png`,
                        )
                      }
                    >
                      <Download className="mr-1 h-3 w-3" />
                      Download
                    </Button>
                  </div>
                  <img
                    src={`data:image/png;base64,${generatedImages.reserves_image}`}
                    alt="Reserves"
                    className="max-w-full rounded-md border border-slate-200"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Delete siege dialog */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Siege</DialogTitle>
            <DialogDescription>
              This action cannot be undone. All buildings and assignments will be permanently
              deleted.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete building dialog */}
      <Dialog
        open={deleteBuildingId != null}
        onOpenChange={(open) => { if (!open) setDeleteBuildingId(null); }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Building</DialogTitle>
            <DialogDescription>
              Remove this building and all its positions from the siege?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteBuildingId(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (deleteBuildingId != null) deleteBuildingMutation.mutate(deleteBuildingId);
              }}
              disabled={deleteBuildingMutation.isPending}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Notify Members confirm dialog */}
      <Dialog open={notifyConfirmOpen} onOpenChange={setNotifyConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Notify Members</DialogTitle>
            <DialogDescription>
              Send Discord DMs to all members with their siege assignments. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNotifyConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => notifyMutation.mutate()}
              disabled={notifyMutation.isPending}
            >
              Send Notifications
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Post to Discord confirm dialog */}
      <Dialog open={postConfirmOpen} onOpenChange={setPostConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Post to Discord</DialogTitle>
            <DialogDescription>
              Post the siege assignment images to the configured Discord channel.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPostConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => postChannelMutation.mutate()}
              disabled={postChannelMutation.isPending}
            >
              Post
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
