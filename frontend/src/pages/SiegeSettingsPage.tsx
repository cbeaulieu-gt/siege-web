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
import type { BuildingType, ValidationResult } from '../api/types';
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
import { ArrowLeft, Trash2, LayoutGrid, MessageSquare, Users } from 'lucide-react';
import { isAxiosError } from 'axios';

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
        <h2 className="mb-4 text-base font-semibold text-slate-900">Lifecycle</h2>
        <div className="flex flex-wrap gap-3">
          {siege?.status === 'planning' && (
            <Button
              variant="default"
              onClick={() => activateMutation.mutate()}
              disabled={activateMutation.isPending}
            >
              Activate
            </Button>
          )}
          {siege?.status === 'active' && (
            <Button
              variant="secondary"
              onClick={() => completeMutation.mutate()}
              disabled={completeMutation.isPending}
            >
              Complete
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
    </div>
  );
}
