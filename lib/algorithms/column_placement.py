# -*- coding: utf-8 -*-
"""
Algorithme placement poteaux v6.0 - UNIVERSEL
CORRECTIONS v6.0 :
1. Détection ouvertures (portes/fenêtres) → décalage sur jambage
2. Espacement minimum 2m strict dans les DEUX sens
3. Espacement max 4m UNIQUEMENT si mur présent pour l'intermédiaire
4. Alignement sur le mur le plus long de chaque axe
"""
from __future__ import division, print_function
import math

try:
    from Autodesk.Revit.DB import (
        XYZ, Line, Grid, Level, Wall,
        FilteredElementCollector, BuiltInCategory,
        Transaction, TransactionGroup, SetComparisonResult,
        BuiltInParameter, ElementId,
        LocationPoint, LocationCurve, FamilyInstance,
    )
    from Autodesk.Revit.DB.Structure import StructuralType
    REVIT_AVAILABLE = True
except Exception:
    REVIT_AVAILABLE = False

try:
    from services.revit_service import RevitService
    from services.geometry_service import GeometryService
    from services.logging_service import LoggingService
    from helpers.revit_helpers import get_all_grids, get_all_levels
    SERVICES_AVAILABLE = True
except Exception:
    SERVICES_AVAILABLE = False

try:
    from utils.decorators import log_execution, transaction, handle_errors
except Exception:
    def log_execution(func): return func
    def transaction(name):
        def d(func): return func
        return d
    def handle_errors(msg):
        def d(func): return func
        return d

# ═══════════════════════════════════════════════════════
#  CONSTANTES
# ═══════════════════════════════════════════════════════
MIN_WALL_HEIGHT_M    = 2.0
MIN_WALL_LENGTH_M    = 0.5
PORTEE_CIBLE_M       = 4.0
PORTEE_MAX_M         = 5.5
PORTEE_MIN_M         = 2.0
ON_WALL_TOL_M        = 0.05
DUP_TOL_M            = 0.10
WALL_TOP_MIN_ABOVE_M   = 0.10
WALL_BASE_MAX_ABOVE_M  = 0.50
TOL_SUPERPOSITION_M    = 0.15
CONTINUITY_MAX_DIST_M  = 0.50
VALIDATE_MAX_DIST_M    = 0.30
# v6.0
OPENING_MARGIN_M       = 0.10
JAMB_OFFSET_M          = 0.05
SPACING_MIN_M          = 2.0
GRID_SNAP_TOL_M        = 0.30

_MOTS_INTER = [
    "techo","toiture","roof","terrasse","terrace","cubierta",
    "patio","rampe","ramp","parking","autos","voiture",
    "pieza","piece","vide","comble","faux","false",
    "palier","landing","rellano","acrotere","acrotera",
]
_MOTS_TOIT = ["toit","roof","techo","cubierta","terrasse","terrace",
              "toiture","acrotere","acrotera"]

def is_intermediate_level(name):
    return any(m in name.lower() for m in _MOTS_INTER)

def is_roof_level(name):
    return any(m in name.lower() for m in _MOTS_TOIT)

def find_next_structural_level(levels_sorted, current_level_id):
    idx = -1
    for i, l in enumerate(levels_sorted):
        if l.Id == current_level_id: idx = i; break
    if idx < 0 or idx >= len(levels_sorted)-1: return None, 3000.0, []
    cur = levels_sorted[idx]; skipped = []
    for j in range(idx+1, len(levels_sorted)):
        c = levels_sorted[j]
        if is_intermediate_level(c.Name): skipped.append(c.Name); continue
        return c, (c.Elevation - cur.Elevation)*304.8, skipped
    fb = levels_sorted[idx+1]
    return fb, (fb.Elevation - cur.Elevation)*304.8, skipped

# ═══════════════════════════════════════════════════════
#  MURS
# ═══════════════════════════════════════════════════════
class WallSegment(object):
    def __init__(self, x1, y1, x2, y2, height_m, length_m,
                 wall_id=None, base_elev_m=0.0, top_elev_m=0.0):
        self.x1=x1; self.y1=y1; self.x2=x2; self.y2=y2
        self.height_m=height_m; self.length_m=length_m
        self.wall_id=wall_id; self.base_elev_m=base_elev_m; self.top_elev_m=top_elev_m
        dx=x2-x1; dy=y2-y1
        self.angle_deg = abs(math.degrees(math.atan2(abs(dy),abs(dx))))
        self.is_horizontal = self.angle_deg <= 15.0
        self.is_vertical   = self.angle_deg >= 75.0
        self.axis_pos = (y1+y2)/2. if self.is_horizontal else (x1+x2)/2.
        if self.is_horizontal:
            self.span_min=min(x1,x2); self.span_max=max(x1,x2)
        else:
            self.span_min=min(y1,y2); self.span_max=max(y1,y2)

    def project_point(self, px, py):
        dx=self.x2-self.x1; dy=self.y2-self.y1; l2=dx*dx+dy*dy
        if l2<1e-12: return self.x1,self.y1,math.sqrt((px-self.x1)**2+(py-self.y1)**2)
        t=max(0.,min(1.,((px-self.x1)*dx+(py-self.y1)*dy)/l2))
        cx=self.x1+t*dx; cy=self.y1+t*dy
        return cx,cy,math.sqrt((px-cx)**2+(py-cy)**2)

    def distance_to_point(self,px,py):
        _,_,d=self.project_point(px,py); return d

def _wall_covers_level(base_m, top_m, level_m):
    return (top_m > level_m+WALL_TOP_MIN_ABOVE_M and
            base_m <= level_m+WALL_BASE_MAX_ABOVE_M)

def _get_wall_elevation_m(w):
    base_ft=top_ft=0.0
    try:
        bb=w.get_BoundingBox(None)
        if bb: base_ft=bb.Min.Z; top_ft=bb.Max.Z
    except: pass
    height_m=(top_ft-base_ft)*0.3048
    if height_m<0.1:
        try:
            hp=w.get_Parameter(BuiltInParameter.WALL_USER_HEIGHT_PARAM)
            if hp and hp.HasValue: height_m=hp.AsDouble()*0.3048
        except: pass
        if height_m<0.1: height_m=3.0
        top_ft=base_ft+height_m/0.3048
    return base_ft*0.3048, top_ft*0.3048

def _collect_walls_for_level(doc, level_elev_m, log_fn=None):
    log=log_fn or print
    segments=[]; skip_short=skip_height=skip_level=0; total=0
    for w in FilteredElementCollector(doc).OfClass(Wall).ToElements():
        total+=1
        try:
            loc=w.Location
            if not hasattr(loc,'Curve'): continue
            curve=loc.Curve; p1=curve.GetEndPoint(0); p2=curve.GetEndPoint(1)
            dx=p2.X-p1.X; dy=p2.Y-p1.Y
            length_m=math.sqrt(dx*dx+dy*dy)*0.3048
            if length_m<MIN_WALL_LENGTH_M: skip_short+=1; continue
            base_m,top_m=_get_wall_elevation_m(w)
            height_m=top_m-base_m
            if height_m<0.1: height_m=3.0
            if height_m<MIN_WALL_HEIGHT_M: skip_height+=1; continue
            if not _wall_covers_level(base_m,top_m,level_elev_m): skip_level+=1; continue
            segments.append(WallSegment(p1.X,p1.Y,p2.X,p2.Y,height_m,length_m,
                wall_id=w.Id.IntegerValue,base_elev_m=base_m,top_elev_m=top_m))
        except: continue
    log("Murs : %d total | %d actifs | %d trop bas (<%.1fm) | %d trop courts | %d hors niveau"%(
        total,len(segments),skip_height,MIN_WALL_HEIGHT_M,skip_short,skip_level))
    return segments

def _collect_all_walls_for_axis(doc, log_fn=None):
    segments=[]
    for w in FilteredElementCollector(doc).OfClass(Wall).ToElements():
        try:
            loc=w.Location
            if not hasattr(loc,'Curve'): continue
            curve=loc.Curve; p1=curve.GetEndPoint(0); p2=curve.GetEndPoint(1)
            dx=p2.X-p1.X; dy=p2.Y-p1.Y
            length_m=math.sqrt(dx*dx+dy*dy)*0.3048
            if length_m<MIN_WALL_LENGTH_M: continue
            base_m,top_m=_get_wall_elevation_m(w)
            height_m=(top_m-base_m) if top_m>base_m else 3.0
            segments.append(WallSegment(p1.X,p1.Y,p2.X,p2.Y,height_m,length_m,
                wall_id=w.Id.IntegerValue,base_elev_m=base_m,top_elev_m=top_m))
        except: continue
    return segments

# ═══════════════════════════════════════════════════════
#  DÉTECTION OUVERTURES v6.0
# ═══════════════════════════════════════════════════════
class Opening(object):
    def __init__(self, center_x, center_y, width_m, is_horizontal,
                 wall_axis_pos):
        self.cx=center_x; self.cy=center_y; self.width_m=width_m
        self.is_horizontal=is_horizontal; self.wall_axis_pos=wall_axis_pos
        half=(width_m/0.3048)/2.0 + OPENING_MARGIN_M/0.3048
        if is_horizontal:
            self.pos_min=center_x-half; self.pos_max=center_x+half
        else:
            self.pos_min=center_y-half; self.pos_max=center_y+half

    def contains_pos(self, pos):
        return self.pos_min <= pos <= self.pos_max

    def jamb_positions(self):
        joff=JAMB_OFFSET_M/0.3048
        return (self.pos_min-joff, self.pos_max+joff)

def _collect_openings_for_level(doc, level_elev_m, wall_segs, log_fn=None):
    log=log_fn or print; openings=[]
    tol_axis=0.5/0.3048
    for cat in [BuiltInCategory.OST_Doors, BuiltInCategory.OST_Windows]:
        try:
            elems=(FilteredElementCollector(doc)
                   .OfCategory(cat).OfClass(FamilyInstance).ToElements())
            for elem in elems:
                try:
                    loc=elem.Location
                    if not isinstance(loc,LocationPoint): continue
                    pt=loc.Point; z_m=pt.Z*0.3048
                    if abs(z_m-level_elev_m)>5.0: continue
                    host=elem.Host
                    if host is None: continue
                    host_loc=host.Location
                    if not hasattr(host_loc,'Curve'): continue
                    hcurve=host_loc.Curve
                    hp1=hcurve.GetEndPoint(0); hp2=hcurve.GetEndPoint(1)
                    hdx=hp2.X-hp1.X; hdy=hp2.Y-hp1.Y
                    hangle=abs(math.degrees(math.atan2(abs(hdy),abs(hdx))))
                    is_h=hangle<=15.0; is_v=hangle>=75.0
                    if not (is_h or is_v): continue
                    width_m=1.0
                    for pname in ["Largeur","Width","w","rough_width","Rough Width"]:
                        try:
                            p=elem.Symbol.LookupParameter(pname)
                            if p and p.HasValue: width_m=p.AsDouble()*0.3048; break
                        except: pass
                    if width_m<0.3: continue
                    if is_h:
                        wall_axis=(hp1.Y+hp2.Y)/2.
                    else:
                        wall_axis=(hp1.X+hp2.X)/2.
                    openings.append(Opening(
                        center_x=pt.X, center_y=pt.Y, width_m=width_m,
                        is_horizontal=is_h, wall_axis_pos=wall_axis))
                except: continue
        except: continue
    log("  Ouvertures détectées : %d"%len(openings))
    return openings

def _adjust_for_openings(positions, openings, is_horizontal, axis_pos,
                          wall_segs, log_fn):
    log=log_fn or print
    tol_axis=0.5/0.3048
    tol_wall=ON_WALL_TOL_M/0.3048*5
    min_ft=PORTEE_MIN_M/0.3048
    result=[]; n_moved=0; n_del=0
    rel=[o for o in openings
         if o.is_horizontal==is_horizontal
         and abs(o.wall_axis_pos-axis_pos)<tol_axis]

    for pt in positions:
        pos=pt[0] if is_horizontal else pt[1]
        in_op=None
        for op in rel:
            if op.contains_pos(pos): in_op=op; break
        if in_op is None: result.append(pt); continue

        j1,j2=in_op.jamb_positions()
        d1=abs(pos-j1); d2=abs(pos-j2)
        candidates=[j1,j2] if d1<=d2 else [j2,j1]

        def jamb_ok(j):
            for o2 in rel:
                if o2 is not in_op and o2.contains_pos(j): return False
            px2=(j,axis_pos) if is_horizontal else (axis_pos,j)
            return any(s.distance_to_point(px2[0],px2[1])<=tol_wall for s in wall_segs)

        moved=None
        for j_c in candidates:
            if jamb_ok(j_c):
                moved=(j_c,axis_pos) if is_horizontal else (axis_pos,j_c)
                break

        if moved is None:
            log("    Ouverture : poteau %.2fm supprimé (jambages invalides)"%(pos*0.3048))
            n_del+=1; continue

        orig=pos; new=moved[0] if is_horizontal else moved[1]
        log("    Ouverture : %.2fm → jambage %.2fm"%(orig*0.3048,new*0.3048))
        result.append(moved); n_moved+=1

    if n_moved or n_del:
        log("  Ouvertures : %d déplacés | %d supprimés"%(n_moved,n_del))
    return result

# ═══════════════════════════════════════════════════════
#  GROUPEMENT MURS
# ═══════════════════════════════════════════════════════
def _group_collinear_walls(segments, tol_axis_m=0.20):
    tol_ft=tol_axis_m/0.3048
    h_groups={}; v_groups={}
    for seg in segments:
        if seg.is_horizontal:
            placed=False
            for key in list(h_groups.keys()):
                if abs(seg.axis_pos-key)<tol_ft: h_groups[key].append(seg); placed=True; break
            if not placed: h_groups[seg.axis_pos]=[seg]
        elif seg.is_vertical:
            placed=False
            for key in list(v_groups.keys()):
                if abs(seg.axis_pos-key)<tol_ft: v_groups[key].append(seg); placed=True; break
            if not placed: v_groups[seg.axis_pos]=[seg]
    return {'H':h_groups,'V':v_groups}

def _merge_wall_group_extent(wall_list):
    span_min=min(w.span_min for w in wall_list)
    span_max=max(w.span_max for w in wall_list)
    total_length=sum(w.length_m for w in wall_list)
    axis_pos_avg=sum(w.axis_pos for w in wall_list)/len(wall_list)
    return span_min,span_max,total_length,axis_pos_avg

def _detect_dominant_axis(wall_groups, log_fn=None):
    log=log_fn or print
    total_h=sum(sum(w.length_m for w in wl) for wl in wall_groups['H'].values())
    total_v=sum(sum(w.length_m for w in wl) for wl in wall_groups['V'].values())
    dominant='H' if total_h>=total_v else 'V'
    log("  Axe dominant : %s (H=%.1fm | V=%.1fm) → b dans sens %s"%(
        dominant,total_h,total_v,
        'X (horizontal)' if dominant=='H' else 'Y (vertical)'))
    return dominant

# ═══════════════════════════════════════════════════════
#  PLACEMENT v6.0 : espacement max = 4m AVEC MUR
# ═══════════════════════════════════════════════════════
def _place_columns_on_wall_segment(span_min, span_max, axis_pos,
                                    portee_cible_ft, portee_max_ft,
                                    portee_min_ft, is_horizontal,
                                    wall_segs, log_fn):
    """
    v6.0 : Place des poteaux sur un mur.
    Règle : on n'insère un poteau intermédiaire QUE si un mur perpendiculaire
    se trouve dans l'intervalle. Si la travée dépasse 4m sans mur → on garde
    les extrémités seulement (pas de poteau fictif dans le vide).
    """
    log=log_fn or print
    total_m=(span_max-span_min)*0.3048
    if total_m<portee_min_ft*0.3048:
        return ([(span_min,axis_pos),(span_max,axis_pos)] if is_horizontal
                else [(axis_pos,span_min),(axis_pos,span_max)])

    # Positions des murs perpendiculaires dans l'intervalle
    perp=[]
    for seg in wall_segs:
        if is_horizontal and seg.is_vertical:
            if seg.span_min<=axis_pos<=seg.span_max:
                pos=seg.axis_pos
                if span_min<pos<span_max: perp.append(pos)
        elif not is_horizontal and seg.is_horizontal:
            if seg.span_min<=axis_pos<=seg.span_max:
                pos=seg.axis_pos
                if span_min<pos<span_max: perp.append(pos)
    perp=sorted(set(perp))

    all_breaks=sorted(set([span_min]+perp+[span_max]))
    final=[span_min]

    for i in range(len(all_breaks)-1):
        seg_s=all_breaks[i]; seg_e=all_breaks[i+1]
        seg_len_m=(seg_e-seg_s)*0.3048
        if seg_len_m<=portee_max_ft:
            # Sous-travée OK → seulement l'extrémité finale
            final.append(seg_e)
        else:
            # Sous-travée > 4m SANS mur intermédiaire connu
            # Subdiviser en portées régulières UNIQUEMENT si un mur se trouve
            # dans cette zone (tolérance élargie)
            tol_broad=1.5/0.3048
            intermediates_found=[]
            for seg in wall_segs:
                if is_horizontal and seg.is_vertical:
                    pos=seg.axis_pos
                    if seg_s<pos<seg_e:
                        intermediates_found.append(pos)
                elif not is_horizontal and seg.is_horizontal:
                    pos=seg.axis_pos
                    if seg_s<pos<seg_e:
                        intermediates_found.append(pos)

            if intermediates_found:
                # Des murs existent → on peut subdiviser
                n=max(1,int(math.ceil(seg_len_m/portee_cible_ft)))
                portee_res=seg_len_m/n
                log("    Subdivision %.2fm → %d intervalles de %.2fm"%(
                    seg_len_m,n,portee_res))
                for j in range(1,n):
                    t=j/float(n)
                    pos=seg_s+t*(seg_e-seg_s)
                    # Snap sur le mur intermédiaire le plus proche
                    best_snap=None; best_d=tol_broad
                    for mp in intermediates_found:
                        d=abs(pos-mp)
                        if d<best_d: best_d=d; best_snap=mp
                    if best_snap is not None:
                        final.append(best_snap)
                        log("    Intermédiaire snappé sur mur : %.2fm"%(best_snap*0.3048))
                    else:
                        log("    Intermédiaire %.2fm ignoré (pas de mur proche)"%(pos*0.3048))
            else:
                # Aucun mur dans l'intervalle → pas de poteau intermédiaire
                log("    Travée %.2fm > max (%.1fm) SANS mur → pas d'intermédiaire"%(
                    seg_len_m,PORTEE_MAX_M))
            final.append(seg_e)

    final=sorted(set(final))
    log("    Mur %.2fm : %d poteaux"%(total_m,len(final)))
    if is_horizontal: return [(p,axis_pos) for p in final]
    else:             return [(axis_pos,p) for p in final]

def _snap_to_perpendicular_walls(positions, wall_segs, is_horizontal,
                                  axis_pos, tol_ft, log_fn):
    log=log_fn or print; perp=[]
    for seg in wall_segs:
        if is_horizontal and seg.is_vertical:
            if seg.span_min<=axis_pos<=seg.span_max: perp.append(seg.axis_pos)
        elif not is_horizontal and seg.is_horizontal:
            if seg.span_min<=axis_pos<=seg.span_max: perp.append(seg.axis_pos)
    snap_ft=0.5/0.3048; adjusted=[]
    for pt in positions:
        coord=pt[0] if is_horizontal else pt[1]
        best_pp=None; best_d=snap_ft
        for pp in perp:
            d=abs(coord-pp)
            if d<best_d: best_d=d; best_pp=pp
        if best_pp is not None:
            log("    Snap mur perp : %.3fm → %.3fm"%(coord*0.3048,best_pp*0.3048))
            adjusted.append((best_pp,axis_pos) if is_horizontal else (axis_pos,best_pp))
        else: adjusted.append(pt)
    return adjusted

# ═══════════════════════════════════════════════════════
#  ESPACEMENT MINIMUM STRICT v6.0
# ═══════════════════════════════════════════════════════
def _enforce_min_spacing_strict(pts_xy, min_m, log_fn):
    """
    v6.0 : Espacement minimum dans les DEUX sens.
    Distance euclidienne < min_m entre deux poteaux → supprimer le second.
    """
    log=log_fn or print; min_ft=min_m/0.3048
    kept=[]; removed=0
    sorted_pts=sorted(pts_xy,key=lambda p:(round(p[0]*10),round(p[1]*10)))
    for px,py in sorted_pts:
        too_close=any(math.sqrt((px-kx)**2+(py-ky)**2)<min_ft for kx,ky in kept)
        if too_close: removed+=1
        else: kept.append((px,py))
    if removed: log("  Espacement min %.1fm (strict) : %d supprimés"%(min_m,removed))
    return kept

# ═══════════════════════════════════════════════════════
#  ALIGNEMENT SUR LE MUR LE PLUS LONG v6.0
# ═══════════════════════════════════════════════════════
def _align_to_longest_wall(pts_xy, wall_groups, log_fn):
    """
    v6.0 : Snap les poteaux sur la grille du mur le plus long
    de chaque axe (H et V).
    """
    log=log_fn or print; snap_ft=GRID_SNAP_TOL_M/0.3048; adjusted=list(pts_xy)
    h_refs=sorted([(sum(w.length_m for w in wl),ay)
                   for ay,wl in wall_groups['H'].items()],reverse=True)
    v_refs=sorted([(sum(w.length_m for w in wl),ax)
                   for ax,wl in wall_groups['V'].items()],reverse=True)
    n_snapped=0
    for i,(px,py) in enumerate(adjusted):
        new_px=px; new_py=py
        for _,ref_y in h_refs:
            if 0<abs(py-ref_y)<snap_ft: new_py=ref_y; n_snapped+=1; break
        for _,ref_x in v_refs:
            if 0<abs(px-ref_x)<snap_ft: new_px=ref_x; n_snapped+=1; break
        adjusted[i]=(new_px,new_py)
    if n_snapped: log("  Alignement mur le plus long : %d snappés"%n_snapped)
    return adjusted

# ═══════════════════════════════════════════════════════
#  CONTINUITÉ ET VALIDATION
# ═══════════════════════════════════════════════════════
def _apply_strict_vertical_continuity(pts_current, pts_reference, wall_segs, log_fn):
    log=log_fn or print; tol_dup=TOL_SUPERPOSITION_M/0.3048
    result=[]; n_ref=0; n_skip=0
    for rpx,rpy in pts_reference:
        if wall_segs:
            nearest=min(wall_segs,key=lambda s:s.distance_to_point(rpx,rpy))
            dist_m=nearest.distance_to_point(rpx,rpy)*0.3048
            if dist_m>CONTINUITY_MAX_DIST_M:
                log("  Ref supprimé (pas de mur): (%.2f,%.2f) [%.2fm]"%(
                    rpx*0.3048,rpy*0.3048,dist_m))
                n_skip+=1; continue
            if dist_m>ON_WALL_TOL_M:
                nx,ny,_=nearest.project_point(rpx,rpy); result.append((nx,ny))
            else: result.append((rpx,rpy))
        else: result.append((rpx,rpy))
        n_ref+=1
    n_extra=0
    for px,py in pts_current:
        already=any(math.sqrt((px-rx)**2+(py-ry)**2)<tol_dup for rx,ry in result)
        if not already:
            result.append((px,py)); n_extra+=1
            log("  Extra ajouté : (%.2f,%.2f)"%(px*0.3048,py*0.3048))
    log("  Continuité stricte : %d ref + %d extra = %d total (%d ignorés)"%(
        n_ref,n_extra,len(result),n_skip))
    return result

def _find_reference_level_name(positions_by_level):
    if not positions_by_level: return None
    return max(positions_by_level,key=lambda k:len(positions_by_level[k]))

def _is_on_any_wall(px,py,segments,tol_ft):
    return any(s.distance_to_point(px,py)<=tol_ft for s in segments)

def _nearest_wall(px,py,segments):
    if not segments: return None
    return min(segments,key=lambda s:s.distance_to_point(px,py))

def _deduplicate(pts,tol_m=DUP_TOL_M):
    tol_ft=tol_m/0.3048; final=[]; seen=[]
    for px,py in pts:
        if any(abs(px-sx)<tol_ft and abs(py-sy)<tol_ft for sx,sy in seen): continue
        seen.append((px,py)); final.append((px,py))
    return final

def _get_building_bbox(segments):
    if not segments: return None
    xs=[s.x1 for s in segments]+[s.x2 for s in segments]
    ys=[s.y1 for s in segments]+[s.y2 for s in segments]
    return (min(xs),max(xs),min(ys),max(ys))

def _validate_on_walls(pts_xy, wall_segs, log_fn):
    log=log_fn or print; tol_ft=ON_WALL_TOL_M/0.3048
    result=[]; n_ok=0; n_corr=0; n_del=0
    for px,py in pts_xy:
        if _is_on_any_wall(px,py,wall_segs,tol_ft):
            result.append((px,py)); n_ok+=1
        else:
            nearest=_nearest_wall(px,py,wall_segs)
            if nearest is None: n_del+=1; continue
            dist_m=nearest.distance_to_point(px,py)*0.3048
            if dist_m<=VALIDATE_MAX_DIST_M:
                nx,ny,_=nearest.project_point(px,py); result.append((nx,ny)); n_corr+=1
            else:
                n_del+=1
                log("  Supprimé hors mur (%.2f,%.2f) [%.2fm]"%(px*0.3048,py*0.3048,dist_m))
    log("  Validation murs : %d OK | %d corrigés | %d supprimés"%(n_ok,n_corr,n_del))
    return result

# ═══════════════════════════════════════════════════════
#  RAPPORT DE NIVEAU
# ═══════════════════════════════════════════════════════
def build_level_report(doc, log_fn=None):
    log=log_fn or print
    levels=sorted(FilteredElementCollector(doc).OfClass(Level).ToElements(),
                  key=lambda l:l.Elevation)
    all_walls=list(FilteredElementCollector(doc).OfClass(Wall).ToElements())
    reports={}
    log("="*60); log("  RAPPORT NIVEAUX"); log("="*60)
    log("%-20s  %8s  %5s  %6s  %s"%("Niveau","Elev(mm)","Murs","H(mm)","Statut"))
    log("-"*60)
    for i,lvl in enumerate(levels):
        elev_m=lvl.Elevation*0.3048; elev_mm=round(elev_m*1000,0)
        h_mm=round((levels[i+1].Elevation-lvl.Elevation)*304.8,0) if i<len(levels)-1 else 3000.0
        murs_actifs=[]
        for w in all_walls:
            try:
                base_m,top_m=_get_wall_elevation_m(w)
                height_m=top_m-base_m if top_m>base_m else 3.0
                if height_m<MIN_WALL_HEIGHT_M: continue
                loc=w.Location
                if not hasattr(loc,'Curve'): continue
                if _wall_covers_level(base_m,top_m,elev_m):
                    curve=loc.Curve; p1=curve.GetEndPoint(0); p2=curve.GetEndPoint(1)
                    length_m=math.sqrt((p2.X-p1.X)**2+(p2.Y-p1.Y)**2)*0.3048
                    murs_actifs.append({"id":w.Id.IntegerValue,
                        "base_mm":round(base_m*1000,0),"top_mm":round(top_m*1000,0),
                        "len_mm":round(length_m*1000,0),
                        "x1":p1.X,"y1":p1.Y,"x2":p2.X,"y2":p2.Y})
            except: continue
        nb=len(murs_actifs)
        statut=("VIDE" if nb==0 else ("FAIBLE(%d)"%nb if nb<3 else "OK(%d)"%nb))
        if is_intermediate_level(lvl.Name): statut+=" [INTER]"
        if is_roof_level(lvl.Name): statut+=" [TOIT]"
        log("%-20s  %8.0f  %5d  %6.0f  %s"%(lvl.Name,elev_mm,nb,h_mm,statut))
        reports[lvl.Name]={
            "level":lvl,"elev_m":elev_m,"elev_mm":elev_mm,"h_etage_mm":h_mm,
            "nb_murs":nb,"murs":murs_actifs,"statut":statut,
            "is_vide":nb==0,"is_ok":nb>=3,
            "is_intermediate":is_intermediate_level(lvl.Name),
            "is_roof":is_roof_level(lvl.Name)}
    log("="*60)
    vides=[n for n,r in reports.items() if r["is_vide"] and not r["is_roof"]]
    if vides: log("NIVEAUX SANS MURS : %s"%", ".join(vides))
    return reports

# ═══════════════════════════════════════════════════════
#  VALIDATION GRILLES / NIVEAUX
# ═══════════════════════════════════════════════════════
_TOL_DUPLICATE_GRID_MM=50.0; _MIN_GRID_LENGTH_M=1.0
_TOL_DUPLICATE_LEVEL_MM=10.0; _GAP_LOW_M=0.30; _GAP_HIGH_M=15.0

def _analyze_single_grid(grid):
    try:
        curve=grid.Curve; start=curve.GetEndPoint(0); end=curve.GetEndPoint(1)
        dx=end.X-start.X; dy=end.Y-start.Y
        length_m=math.sqrt(dx*dx+dy*dy)*0.3048
        angle_deg=abs(math.degrees(math.atan2(abs(dy),abs(dx))))
        is_diag=10.<angle_deg<80.; is_v=angle_deg>=80.; is_h=angle_deg<=10.
        pos=0.; et="?"
        if is_v: pos=(start.X+end.X)/2.; et="X"
        elif is_h: pos=(start.Y+end.Y)/2.; et="Y"
        return {'name':grid.Name,'id':grid.Id,'element':grid,
                'angle_deg':angle_deg,'length_m':length_m,
                'is_vertical':is_v,'is_horizontal':is_h,'is_diagonal':is_diag,
                'is_too_short':length_m<_MIN_GRID_LENGTH_M,
                'position_ft':pos,'position_m':pos*0.3048,'start':start,'end':end}
    except Exception as e:
        return {'name':getattr(grid,'Name','?'),'id':grid.Id,'element':grid,'error':str(e)}

def _find_duplicate_grids(gas,tol_mm=_TOL_DUPLICATE_GRID_MM):
    tol=tol_mm/304.8; dups=[]; proc=set()
    for fam in [[g for g in gas if g.get('is_vertical') and not g.get('error')],
                [g for g in gas if g.get('is_horizontal') and not g.get('error')]]:
        for i,ga in enumerate(fam):
            if ga['id'].IntegerValue in proc: continue
            grp=[ga]
            for j,gb in enumerate(fam):
                if i==j or gb['id'].IntegerValue in proc: continue
                if abs(ga['position_ft']-gb['position_ft'])<tol:
                    grp.append(gb); proc.add(gb['id'].IntegerValue)
            if len(grp)>1: dups.append((grp[0],grp[1:])); proc.add(ga['id'].IntegerValue)
    return dups

def _analyze_single_level(level,all_sorted):
    try:
        idx=all_sorted.index(level); em=level.Elevation*0.3048
        hm=gp=None
        if idx<len(all_sorted)-1: hm=(all_sorted[idx+1].Elevation-level.Elevation)*0.3048
        if idx>0: gp=(level.Elevation-all_sorted[idx-1].Elevation)*0.3048
        return {'name':level.Name,'id':level.Id,'element':level,
                'elevation_m':em,'height_to_next_m':hm,'gap_from_prev_m':gp,'index':idx,
                'is_negative':em<-0.5,
                'is_very_low_gap':gp is not None and gp<_GAP_LOW_M,
                'is_very_high_gap':gp is not None and gp>_GAP_HIGH_M,
                'is_intermediate':is_intermediate_level(level.Name)}
    except Exception as e:
        return {'name':getattr(level,'Name','?'),'id':level.Id,'element':level,'error':str(e)}

def _find_duplicate_levels(las,tol_mm=_TOL_DUPLICATE_LEVEL_MM):
    tol=tol_mm/1000.; dups=[]; proc=set()
    for i,la in enumerate(las):
        if la['id'].IntegerValue in proc or la.get('error'): continue
        grp=[la]
        for j,lb in enumerate(las):
            if i==j or lb['id'].IntegerValue in proc or lb.get('error'): continue
            if abs(la['elevation_m']-lb['elevation_m'])<tol:
                grp.append(lb); proc.add(lb['id'].IntegerValue)
        if len(grp)>1: dups.append((grp[0],grp[1:])); proc.add(la['id'].IntegerValue)
    return dups

def validate_grids(doc):
    grids=list(FilteredElementCollector(doc).OfClass(Grid))
    res={'valid':[],'diagonal':[],'too_short':[],'duplicates':[],'errors':[],'all':[]}
    for g in grids:
        a=_analyze_single_grid(g); res['all'].append(a)
        if a.get('error'): res['errors'].append(a)
        elif a['is_diagonal']: res['diagonal'].append(a)
        elif a['is_too_short']: res['too_short'].append(a)
        else: res['valid'].append(a)
    res['duplicates']=_find_duplicate_grids(res['valid'])
    res['summary']="=== GRILLES : %d | Valides: %d | Diag: %d ===" % (
        len(grids),len(res['valid']),len(res['diagonal']))
    return res

def validate_levels(doc):
    levels=sorted(list(FilteredElementCollector(doc).OfClass(Level)),key=lambda l:l.Elevation)
    res={'valid':[],'negative':[],'low_gap':[],'high_gap':[],'intermediate':[],
         'duplicates':[],'errors':[],'all':[]}
    anals=[]
    for l in levels:
        a=_analyze_single_level(l,levels); anals.append(a); res['all'].append(a)
        if a.get('error'): res['errors'].append(a); continue
        issues=[]
        if a['is_negative']: issues.append('neg'); res['negative'].append(a)
        if a['is_very_low_gap']: issues.append('low'); res['low_gap'].append(a)
        if a['is_very_high_gap']: issues.append('hi'); res['high_gap'].append(a)
        if a['is_intermediate']: res['intermediate'].append(a)
        if not issues: res['valid'].append(a)
    res['duplicates']=_find_duplicate_levels(anals)
    res['summary']="=== NIVEAUX : %d | Valides: %d | Inter: %d ===" % (
        len(levels),len(res['valid']),len(res['intermediate']))
    return res

def _delete_elements_bulk(doc,elements,tname,log_fn):
    from System.Collections.Generic import List as CsList
    ids=CsList[ElementId]()
    for e in elements: ids.Add(e['id'])
    t=Transaction(doc,tname); t.Start()
    try:
        n=doc.Delete(ids).Count; t.Commit(); log_fn("Supprimé %d"%n); return n
    except Exception as ex:
        t.RollBack(); log_fn("ERR: %s"%str(ex)); return 0

def fix_grids(doc,gv,log_fn=None):
    log=log_fn or print; res={'nb_deleted':0}
    if not gv.get('duplicates'): return res
    tg=TransactionGroup(doc,"Fix grilles"); tg.Start()
    try:
        for keep,td in gv['duplicates']:
            res['nb_deleted']+=_delete_elements_bulk(doc,td,"Doublon '%s'"%keep['name'],log)
        tg.Commit()
    except Exception as e: tg.RollBack(); log("ERR:%s"%str(e))
    return res

def fix_levels(doc,lv,log_fn=None):
    log=log_fn or print; res={'nb_deleted':0}
    if not lv.get('duplicates'): return res
    tg=TransactionGroup(doc,"Fix niveaux"); tg.Start()
    try:
        for keep,td in lv['duplicates']:
            res['nb_deleted']+=_delete_elements_bulk(doc,td,"Doublon '%s'"%keep['name'],log)
        tg.Commit()
    except Exception as e: tg.RollBack(); log("ERR:%s"%str(e))
    return res

def run_full_validation_and_fix(doc,auto_fix=True,log_fn=None):
    log=log_fn or print; log("=== VALIDATION ===")
    gr=validate_grids(doc); log(gr['summary'])
    lr=validate_levels(doc); log(lr['summary'])
    fg=fl={'nb_deleted':0}
    if auto_fix:
        fg=fix_grids(doc,gr,log_fn=log); fl=fix_levels(doc,lr,log_fn=log)
    probs=[]
    if gr['diagonal']: probs.append("%d diagonales"%len(gr['diagonal']))
    if lr['intermediate']: probs.append("%d intermédiaires"%len(lr['intermediate']))
    return {'grid_report':gr,'level_report':lr,'fix_grids':fg,'fix_levels':fl,
            'full_summary':"Grilles:%d valides | Niveaux:%d valides"%(
                len(gr['valid']),len(lr['valid'])),
            'has_problems':bool(probs)}

def _get_oriented_section(section,dominant_axis):
    w,h=section; b=max(w,h); a=min(w,h)
    if dominant_axis=='H': return (b,a,0.0)
    else: return (a,b,math.pi/2.0)

# ═══════════════════════════════════════════════════════
#  MOTEUR PRINCIPAL v6.0
# ═══════════════════════════════════════════════════════
class ColumnPlacementEngine:
    STANDARD_SECTIONS=[
        (200,200),(250,250),(250,350),(300,300),(300,400),(350,350),
        (350,500),(400,400),(400,600),(450,450),(500,500),(600,600),
        (800,800),(1000,1000)]
    MAX_SPACING=4000; MIN_WALL_DISTANCE=1500
    HEIGHT_THRESHOLD_1=3000; HEIGHT_THRESHOLD_2=5000

    def __init__(self,doc,api_client=None):
        self.doc=doc; self.api=api_client
        if SERVICES_AVAILABLE:
            self.revit_service=RevitService(doc)
            self.geometry_service=GeometryService(doc)
            self.logger=LoggingService(api_client)
        else:
            self.revit_service=self.geometry_service=self.logger=None
        self._grids_cache=None; self._levels_cache=None
        self._column_types_cache={}; self._last_validation=None
        self._dominant_axis_cache=None; self._all_wall_segs_cache=None
        self._positions_by_level={}; self._reference_pts=None
        self._reference_level_name=None; self._level_reports={}

    def _log(self,message,level='info'):
        if self.logger:
            if level=='info': self.logger.log_info(message)
            elif level=='warning': self.logger.log_warning(message)
            elif level=='error': self.logger.log_error(message,{})
        else: print(message)

    def invalidate_cache(self):
        self._grids_cache=self._levels_cache=None
        self._column_types_cache={}; self._last_validation=None
        self._dominant_axis_cache=None; self._all_wall_segs_cache=None
        self._positions_by_level={}; self._reference_pts=None
        self._reference_level_name=None; self._level_reports={}

    def _get_dominant_axis_cached(self):
        if self._dominant_axis_cache is None:
            self._log("Calcul axe dominant (tous murs)...")
            self._all_wall_segs_cache=_collect_all_walls_for_axis(self.doc,self._log)
            all_groups=_group_collinear_walls(self._all_wall_segs_cache)
            self._dominant_axis_cache=_detect_dominant_axis(all_groups,self._log)
        return self._dominant_axis_cache

    def _get_wall_data_for_level(self,level):
        level_elev_m=level.Elevation*0.3048
        dominant_axis=self._get_dominant_axis_cached()
        wall_segs=_collect_walls_for_level(self.doc,level_elev_m,self._log)
        wall_groups=_group_collinear_walls(wall_segs)
        bbox=_get_building_bbox(wall_segs)
        self._log("Groupes niveau '%s' : %d murs H | %d murs V"%(
            level.Name,len(wall_groups['H']),len(wall_groups['V'])))
        return wall_segs,wall_groups,bbox,dominant_axis

    def _update_reference_level(self):
        if not self._positions_by_level: return
        ref_name=_find_reference_level_name(self._positions_by_level)
        if ref_name!=self._reference_level_name:
            self._reference_level_name=ref_name
            self._reference_pts=self._positions_by_level[ref_name]
            self._log("  → Niveau référence : '%s' (%d poteaux)"%(
                ref_name,len(self._reference_pts)))

    def validate_and_fix(self,auto_fix=True):
        self._log("--- VALIDATION ---")
        r=run_full_validation_and_fix(self.doc,auto_fix,self._log)
        self.invalidate_cache(); self._last_validation=r; return r

    def get_last_validation(self): return self._last_validation

    def load_rules(self,force_refresh=False):
        return {
            'max_spacing':self.MAX_SPACING,'min_wall_distance':self.MIN_WALL_DISTANCE,
            'progression':{'top_floor':(250,250),'mid_floor':(300,300),
                'ground_floor':(400,400),'basement':(600,600),'heavy_load':(1000,1000)},
            'height_requirements':{'under_3m':(250,250),'3_to_5m':(300,300),'over_5m':(400,400)},
            'prefer_rectangular':True,'optimization_enabled':True}

    def calculate_section_by_level(self,li,tot,is_basement=False,lf=1.0):
        r=self.load_rules(); p=r['progression']
        if is_basement: return p['heavy_load'] if lf>1.5 else p['basement']
        if li==0: s=p['ground_floor']
        elif li>=tot-1: s=p['top_floor']
        else:
            pf=1.-(li/float(tot))
            s=(350,350) if pf>0.7 else ((300,300) if pf>0.4 else (250,250))
        if lf>1.2: s=(int(s[0]*1.2),int(s[1]*1.2))
        return self._get_nearest_standard_section(s[0],s[1])

    def _get_nearest_standard_section(self,w,h):
        if w>h: w,h=h,w
        md=float('inf'); best=(w,h)
        for sw,sh in self.STANDARD_SECTIONS:
            d=abs(sw*sh-w*h)
            if d<md: md=d; best=(sw,sh)
        return best

    def optimize_section_shape(self,s):
        w,h=s; b=max(w,h); a=min(w,h)
        if w==h:
            if w==250: b,a=350,250
            elif w==300: b,a=400,250
            elif w==350: b,a=500,300
            elif w==400: b,a=600,300
            elif w==500: b,a=600,400
        return (min(a,b),max(a,b))

    def validate_height_section(self,hm,s):
        w,hs=s; md=min(w,hs); r=self.load_rules()['height_requirements']
        req=(r['under_3m'][0] if hm<=self.HEIGHT_THRESHOLD_1
             else (r['3_to_5m'][0] if hm<=self.HEIGHT_THRESHOLD_2 else r['over_5m'][0]))
        if md<req:
            return False,"Section %dx%d insuffisante pour %.0fmm (min %d)"%(w,hs,hm,req)
        return True,"OK"

    def get_all_grids(self):
        if self._grids_cache: return self._grids_cache
        if SERVICES_AVAILABLE and self.revit_service:
            grids=get_all_grids(self.doc)
        else:
            grids=[{'grid':g,'transform':None}
                   for g in FilteredElementCollector(self.doc).OfClass(Grid)]
        self._grids_cache=grids; return grids

    def get_all_levels(self):
        if self._levels_cache: return self._levels_cache
        if SERVICES_AVAILABLE:
            levels=get_all_levels(self.doc)
        else:
            levels=sorted(FilteredElementCollector(self.doc).OfClass(Level).ToElements(),
                          key=lambda l:l.Elevation)
        self._levels_cache=levels; return levels

    def get_structural_levels(self):
        al=self.get_all_levels()
        st=[l for l in al if not is_intermediate_level(l.Name)]
        sk=[l for l in al if is_intermediate_level(l.Name)]
        if sk: self._log("Niveaux inter ignorés: %s"%", ".join(l.Name for l in sk))
        return st

    def find_placement_points(self,level,hauteur_mm=3000.0,previous_level_name=None):
        self._log("=== Placement v6.0 - %s (h=%.0fmm) ==="%(level.Name,hauteur_mm))
        self._log("  Portée cible=%.1fm | max=%.1fm | min=%.1fm"%(
            PORTEE_CIBLE_M,PORTEE_MAX_M,PORTEE_MIN_M))
        elev=level.Elevation
        wall_segs,wall_groups,bbox,dominant_axis=self._get_wall_data_for_level(level)
        if not wall_segs:
            self._log("NIVEAU VIDE '%s' → aucun poteau"%level.Name,'warning')
            self._positions_by_level[level.Name]=[]
            self._update_reference_level(); return []

        portee_cible_ft=PORTEE_CIBLE_M/0.3048
        portee_max_ft=PORTEE_MAX_M/0.3048
        portee_min_ft=PORTEE_MIN_M/0.3048
        tol_wall_ft=ON_WALL_TOL_M/0.3048
        level_elev_m=elev*0.3048

        # Détecter les ouvertures
        openings=_collect_openings_for_level(self.doc,level_elev_m,wall_segs,self._log)
        all_pts=[]

        # Murs horizontaux
        self._log("  --- Murs Horizontaux ---")
        for axis_y,wall_list in wall_groups['H'].items():
            span_min,span_max,total_len_m,axis_y_avg=_merge_wall_group_extent(wall_list)
            self._log("  H : Y=%.2fm | L=%.2fm | X=[%.2f..%.2f]m"%(
                axis_y_avg*0.3048,total_len_m,span_min*0.3048,span_max*0.3048))
            pts=_place_columns_on_wall_segment(
                span_min,span_max,axis_y_avg,
                portee_cible_ft,portee_max_ft,portee_min_ft,
                is_horizontal=True,wall_segs=wall_segs,log_fn=self._log)
            pts=_snap_to_perpendicular_walls(
                pts,wall_segs,is_horizontal=True,
                axis_pos=axis_y_avg,tol_ft=tol_wall_ft,log_fn=self._log)
            pts=_adjust_for_openings(
                pts,openings,is_horizontal=True,
                axis_pos=axis_y_avg,wall_segs=wall_segs,log_fn=self._log)
            all_pts.extend(pts)
            self._log("    → %d poteaux"%len(pts))

        # Murs verticaux
        self._log("  --- Murs Verticaux ---")
        for axis_x,wall_list in wall_groups['V'].items():
            span_min,span_max,total_len_m,axis_x_avg=_merge_wall_group_extent(wall_list)
            self._log("  V : X=%.2fm | L=%.2fm | Y=[%.2f..%.2f]m"%(
                axis_x_avg*0.3048,total_len_m,span_min*0.3048,span_max*0.3048))
            pts=_place_columns_on_wall_segment(
                span_min,span_max,axis_x_avg,
                portee_cible_ft,portee_max_ft,portee_min_ft,
                is_horizontal=False,wall_segs=wall_segs,log_fn=self._log)
            pts=_snap_to_perpendicular_walls(
                pts,wall_segs,is_horizontal=False,
                axis_pos=axis_x_avg,tol_ft=tol_wall_ft,log_fn=self._log)
            pts=_adjust_for_openings(
                pts,openings,is_horizontal=False,
                axis_pos=axis_x_avg,wall_segs=wall_segs,log_fn=self._log)
            all_pts.extend(pts)
            self._log("    → %d poteaux"%len(pts))

        self._log("  Sous-total brut : %d"%len(all_pts))
        all_pts=_deduplicate(all_pts,tol_m=DUP_TOL_M)
        self._log("  Après dédoublonnage : %d"%len(all_pts))

        # Espacement minimum STRICT
        all_pts=_enforce_min_spacing_strict(all_pts,SPACING_MIN_M,self._log)

        # Alignement mur le plus long
        all_pts=_align_to_longest_wall(all_pts,wall_groups,self._log)

        # Continuité verticale
        if self._reference_pts is not None:
            self._log("  Continuité avec référence '%s' (%d poteaux)"%(
                self._reference_level_name,len(self._reference_pts)))
            all_pts=_apply_strict_vertical_continuity(
                all_pts,self._reference_pts,wall_segs,self._log)
            all_pts=_deduplicate(all_pts)
        else:
            self._log("  (Pas encore de niveau référence)")

        # Validation finale
        all_pts=_validate_on_walls(all_pts,wall_segs,self._log)
        all_pts=_deduplicate(all_pts)

        self._positions_by_level[level.Name]=all_pts
        self._update_reference_level()
        self._log("==> TOTAL %s : %d poteaux | axe dominant : %s"%(
            level.Name,len(all_pts),dominant_axis))

        return [{'point':XYZ(px,py,elev),'grid_v':'mur_v','grid_h':'mur_h',
                 'dominant_axis':dominant_axis} for px,py in all_pts]

    def get_column_family(self,section):
        key="%dx%d"%(section[0],section[1])
        if key in self._column_types_cache: return self._column_types_cache[key]
        coll=(FilteredElementCollector(self.doc)
              .OfCategory(BuiltInCategory.OST_StructuralColumns)
              .WhereElementIsElementType())
        w,h=section; best=None; bd=float('inf'); first=None
        for elem in coll:
            if first is None: first=elem
            if not hasattr(elem,'LookupParameter'): continue
            wv=hv=None
            for pn in ["Largeur","Width","b","bf","d"]:
                try:
                    p=elem.LookupParameter(pn)
                    if p and p.HasValue: wv=p.AsDouble()*304.8; break
                except: pass
            for pn in ["Hauteur","Height","h","d","bf"]:
                try:
                    p=elem.LookupParameter(pn)
                    if p and p.HasValue: hv=p.AsDouble()*304.8; break
                except: pass
            if wv is not None and hv is not None:
                d=abs(wv-w)+abs(hv-h)
                if d<bd: bd=d; best=elem
        if best is None: best=first
        if best:
            nom="?"
            try:
                p=best.LookupParameter("Nom du type")
                if p and p.HasValue: nom=p.AsString() or "?"
            except: pass
            if nom=="?":
                try: nom=best.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM).AsString() or "?"
                except: pass
            self._log("Famille: %s (%dx%dmm)"%(nom,w,h))
            self._column_types_cache[key]=best
        else: self._log("ERREUR: Aucune famille",'error')
        return best

    def create_columns_for_level(self,level,next_level=None,load_factor=1.0,
                                  hauteur_mm=3000.0,previous_level_name=None):
        is_basement=any(x in level.Name.lower() for x in ["sous-sol","basement","sotano"])
        levels=self.get_structural_levels()
        try:
            idx=next((i for i,l in enumerate(levels) if l.Id==level.Id),0)
            tot=len(levels)
        except: idx=0; tot=len(levels)
        section=self.calculate_section_by_level(idx,tot,is_basement,load_factor)
        section=self.optimize_section_shape(section)
        ok,msg=self.validate_height_section(hauteur_mm,section)
        if not ok:
            self._log("Ajustement: %s"%msg,'warning')
            if hauteur_mm<=self.HEIGHT_THRESHOLD_1: section=(250,350)
            elif hauteur_mm<=self.HEIGHT_THRESHOLD_2: section=(300,400)
            else: section=(400,600)
        dominant_axis=self._get_dominant_axis_cached()
        width_x,height_y,rotation=_get_oriented_section(section,dominant_axis)
        col_type=self.get_column_family((width_x,height_y))
        if not col_type: self._log("Pas de famille",'error'); return []
        if not col_type.IsActive:
            t=Transaction(self.doc,"Activer famille"); t.Start()
            col_type.Activate(); self.doc.Regenerate(); t.Commit()
        pts=self.find_placement_points(level,hauteur_mm,previous_level_name)
        created=[]; t=Transaction(self.doc,"Poteaux %s"%level.Name); t.Start()
        try:
            for pd in pts:
                try:
                    col=self.doc.Create.NewFamilyInstance(
                        pd["point"],col_type,level,StructuralType.Column)
                    if abs(rotation)>0.01:
                        try:
                            axis=Line.CreateBound(pd["point"],
                                XYZ(pd["point"].X,pd["point"].Y,pd["point"].Z+1.0))
                            col.Location.Rotate(axis,rotation)
                        except: pass
                    if next_level:
                        tp=col.get_Parameter(BuiltInParameter.FAMILY_TOP_LEVEL_PARAM)
                        if tp: tp.Set(next_level.Id)
                    created.append({"element":col,"id":col.Id,"point":pd["point"],
                                    "section":section,"dominant_axis":dominant_axis})
                except Exception as e:
                    self._log("Err création (%.2f,%.2f): %s"%(
                        pd["point"].X*0.3048,pd["point"].Y*0.3048,str(e)),'error')
            t.Commit()
        except Exception as e:
            t.RollBack(); self._log("Err transaction: %s"%str(e),'error'); return []
        self._log("%d poteaux créés sur %s"%(len(created),level.Name))
        return created

    def create_all_columns(self,validate_first=True):
        vr=None
        if validate_first:
            self._log("Validation..."); vr=self.validate_and_fix(auto_fix=True)
        al=self.get_all_levels()
        if len(al)<2: return {'success':False,'message':'Niveaux insuffisants'}
        sl=self.get_structural_levels()
        if not sl: return {'success':False,'message':'Aucun niveau structurel'}
        self._positions_by_level={}; self._reference_pts=None
        self._reference_level_name=None
        dom=self._get_dominant_axis_cached()
        self._log("=== RAPPORT NIVEAUX ===")
        self._level_reports=build_level_report(self.doc,self._log)
        self._log("=== CREATION v6.0 - %d niveaux structurels ==="%len(sl))
        self._log("  Axe dominant : %s"%dom)
        self._log("  Murs : couverture physique | Ouvertures : auto")
        self._log("  Espacement : min=%.1fm | max=%.1fm (avec mur)"%(
            SPACING_MIN_M,PORTEE_MAX_M))
        results={}; total=0; prev_name=None
        for cur in sl:
            if is_roof_level(cur.Name):
                self._log("Ignoré toit: %s"%cur.Name); continue
            rpt=self._level_reports.get(cur.Name,{})
            if rpt.get('is_vide',False):
                self._log("Ignoré VIDE '%s'"%cur.Name,'warning'); continue
            nxt,h_mm,skipped=find_next_structural_level(al,cur.Id)
            self._log("\n--- %s → %s (%.0fmm) ---"%(
                cur.Name,nxt.Name if nxt else "fin",h_mm))
            cols=self.create_columns_for_level(
                cur,nxt,load_factor=1.0,hauteur_mm=h_mm,previous_level_name=prev_name)
            results[cur.Name]={'count':len(cols),'columns':cols,'hauteur_mm':h_mm,
                'next_level':nxt.Name if nxt else None,'skipped':skipped,
                'nb_murs':rpt.get('nb_murs',0),
                'is_reference':cur.Name==self._reference_level_name}
            total+=len(cols); prev_name=cur.Name
        self._log("\n=== TOTAL : %d poteaux ==="%total)
        self._log("=== Niveau référence : %s ==="%self._reference_level_name)
        for lname,pts in self._positions_by_level.items():
            tag=" ← RÉFÉRENCE" if lname==self._reference_level_name else ""
            self._log("  %s : %d poteaux%s"%(lname,len(pts),tag))
        return {'success':True,'total_columns':total,'by_level':results,
                'validation_report':vr,'reference_level':self._reference_level_name,
                'level_reports':self._level_reports}

    def check_existing_columns(self,level,tolerance_mm=50.):
        tol=tolerance_mm/304.8
        pts=self.find_placement_points(level)
        cols=(FilteredElementCollector(self.doc)
              .OfCategory(BuiltInCategory.OST_StructuralColumns)
              .WhereElementIsNotElementType().ToElements())
        exist=[]
        for col in cols:
            try:
                loc=col.Location
                if isinstance(loc,LocationPoint): pt=loc.Point
                elif isinstance(loc,LocationCurve): pt=loc.Curve.GetEndPoint(0)
                else: continue
                col_z_m=pt.Z*0.3048; lvl_z_m=level.Elevation*0.3048
                if abs(col_z_m-lvl_z_m)>0.5: continue
                exist.append({'point':pt,'element_id':col.Id.IntegerValue,'element':col})
            except: continue
        new_pts=[]; dups=[]
        for pd in pts:
            pt=pd['point']; found=False
            for ex in exist:
                ep=ex['point']
                if abs(pt.X-ep.X)<tol and abs(pt.Y-ep.Y)<tol:
                    dups.append({'point_data':pd,'element_id':ex['element_id']}); found=True; break
            if not found: new_pts.append(pd)
        self._log("'%s': %d existants | %d doublons | %d nouveaux"%(
            level.Name,len(exist),len(dups),len(new_pts)))
        return {'existing':exist,'new_points':new_pts,'duplicates':dups}

    def find_grid_intersections(self):
        import clr
        try: from Autodesk.Revit.DB import IntersectionResultArray as _IRA
        except: return []
        ag=self.get_all_grids(); vg=[]; hg=[]
        for item in ag:
            g=item['grid']; tr=item.get('transform')
            try:
                c=g.Curve
                s=tr.OfPoint(c.GetEndPoint(0)) if tr else c.GetEndPoint(0)
                e=tr.OfPoint(c.GetEndPoint(1)) if tr else c.GetEndPoint(1)
                lm=math.sqrt((e.X-s.X)**2+(e.Y-s.Y)**2)*0.3048
                if lm<2.: continue
                dx=abs(e.X-s.X); dy=abs(e.Y-s.Y); tot=dx+dy
                if tot<1e-6 or max(dx,dy)/tot<0.8: continue
                d='horizontal' if dx>dy else 'vertical'
                ent={'grid':g,'transform':tr,'start':s,'end':e,
                     'name':g.Name if hasattr(g,'Name') else '?'}
                if d=='horizontal': hg.append(ent)
                else: vg.append(ent)
            except: continue
        ints=[]; tol=10./304.8
        for v in vg:
            for h in hg:
                try:
                    vl=Line.CreateBound(v['start'],v['end'])
                    hl=Line.CreateBound(h['start'],h['end'])
                    box=clr.StrongBox[_IRA]()
                    if vl.Intersect(hl,box)==SetComparisonResult.Overlap and box.Value:
                        for res in box.Value:
                            pt=res.XYZPoint
                            ints.append({'point':pt,'grid_v':v['name'],'grid_h':h['name'],
                                         'pos_v':(v['start'].X+v['end'].X)/2.,
                                         'pos_h':(h['start'].Y+h['end'].Y)/2.})
                except: continue
        return ints

# ═══════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ═══════════════════════════════════════════════════════
def main():
    try:
        from pyrevit import revit, forms
        doc=revit.doc; engine=ColumnPlacementEngine(doc)
        val=engine.validate_and_fix(auto_fix=True)
        if val['has_problems']:
            if not forms.alert(val['full_summary']+"\n\nContinuer ?",ok=False,yes=True,no=True): return
        if forms.alert(
            "Créer les poteaux (v6.0 — UNIVERSEL) ?\n\n"
            "• Portée cible : %.1fm | max : %.1fm\n"
            "• Espacement minimum : %.1fm (strict, 2 sens)\n"
            "• Intermédiaire : uniquement si mur présent\n"
            "• Ouvertures : détection auto portes/fenêtres\n"
            "• Alignement : mur le plus long de chaque axe\n"
            "• Niveaux vides → bloqués sans FALLBACK\n"
            "• Continuité max : %.1fm du mur le plus proche"%(
                PORTEE_CIBLE_M,PORTEE_MAX_M,SPACING_MIN_M,CONTINUITY_MAX_DIST_M),
            ok=False,yes=True,no=True):
            r=engine.create_all_columns(validate_first=False)
            if r['success']:
                lines=["OK - %d poteaux créés !"%r['total_columns'],
                       "Niveau référence : %s"%r.get('reference_level','?'),""]
                for lvl,d in sorted(r['by_level'].items()):
                    tag=" [REF]" if d.get('is_reference') else ""
                    lines.append("  %s : %d poteaux | %d murs%s"%(
                        lvl,d['count'],d.get('nb_murs',0),tag))
                forms.alert("\n".join(lines))
            else: forms.alert("Erreur : %s"%r.get('message','?'))
    except Exception as e:
        import traceback
        print("Erreur: %s"%traceback.format_exc())

if __name__=='__main__':
    main()