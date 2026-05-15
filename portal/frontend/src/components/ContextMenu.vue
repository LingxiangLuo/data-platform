<template>
  <Teleport to="body">
    <Transition name="menu-fade">
      <div v-if="visible" class="context-menu-overlay" @click="onOverlayClick">
        <div
          ref="menuRef"
          class="context-menu"
          :style="menuStyle"
          @click.stop
        >
          <MenuList :items="items" @select="onSelect" />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'

export interface MenuItem {
  key?: string
  label?: string
  icon?: string
  disabled?: boolean
  danger?: boolean
  children?: MenuItem[]
  divider?: boolean
}

const props = defineProps<{
  visible: boolean
  x: number
  y: number
  items: MenuItem[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'select', key: string): void
}>()

const menuRef = ref<HTMLElement>()

const menuStyle = computed(() => {
  let left = props.x
  let top = props.y
  return {
    left: `${left}px`,
    top: `${top}px`,
  }
})

function close() {
  emit('update:visible', false)
}

function onOverlayClick() {
  close()
}

function onSelect(key: string) {
  emit('select', key)
  close()
}

watch(() => props.visible, (v) => {
  if (v) {
    nextTick(() => {
      const handler = (e: MouseEvent) => {
        if (!menuRef.value?.contains(e.target as Node)) {
          close()
          document.removeEventListener('mousedown', handler)
        }
      }
      document.addEventListener('mousedown', handler)
    })
  }
})
</script>

<script lang="ts">
import { h, defineComponent } from 'vue'

const MenuList: any = defineComponent({
  name: 'MenuList',
  props: {
    items: { type: Array as () => MenuItem[], required: true },
    nested: { type: Boolean, default: false },
  },
  emits: ['select'],
  setup(props: { items: MenuItem[]; nested: boolean }, { emit }: { emit: (e: 'select', key: string) => void }) {
    const activeKey = ref<string | null>(null)
    let hideTimer: any = null

    function onItemClick(item: MenuItem) {
      if (item.disabled || item.children?.length) return
      emit('select', item.key!)
    }

    function onMouseEnter(item: MenuItem) {
      if (hideTimer) {
        clearTimeout(hideTimer)
        hideTimer = null
      }
      if (item.children?.length) {
        activeKey.value = item.key ?? null
      } else {
        activeKey.value = null
      }
    }

    function onMouseLeave() {
      hideTimer = setTimeout(() => {
        activeKey.value = null
      }, 150)
    }

    return (): any => h('ul', { class: ['menu-list', { 'menu-nested': props.nested }] },
      props.items.map((item): any => {
        if (item.divider) {
          return h('li', { class: 'menu-divider' })
        }
        const hasChildren = !!item.children?.length
        const isActive = activeKey.value === item.key
        return h('li', {
          class: [
            'menu-item',
            {
              'menu-disabled': item.disabled,
              'menu-danger': item.danger,
              'menu-active': isActive,
              'menu-has-children': hasChildren,
            },
          ],
          onClick: () => onItemClick(item),
          onMouseenter: () => onMouseEnter(item),
          onMouseleave: onMouseLeave,
        }, [
          h('span', { class: 'menu-label' }, item.label),
          hasChildren && h('span', { class: 'menu-arrow' }, '▶'),
          hasChildren && isActive && h('div', {
            class: 'menu-submenu',
            onMouseenter: () => {
              if (hideTimer) { clearTimeout(hideTimer); hideTimer = null }
              activeKey.value = item.key ?? null
            },
            onMouseleave: onMouseLeave,
          }, [
            h(MenuList, {
              items: item.children!,
              nested: true,
              onSelect: (key: string) => emit('select', key),
            }),
          ]),
        ])
      })
    )
  },
})
</script>

<style scoped>
.context-menu-overlay {
  position: fixed;
  inset: 0;
  z-index: 9998;
}

.context-menu {
  position: fixed;
  z-index: 9999;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20px) saturate(1.8);
  -webkit-backdrop-filter: blur(20px) saturate(1.8);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.04),
    0 4px 8px rgba(0, 0, 0, 0.04),
    0 12px 24px rgba(0, 0, 0, 0.08),
    0 24px 48px rgba(0, 0, 0, 0.06);
  padding: 6px 0;
  min-width: 180px;
  font-size: 13px;
  line-height: 1;
  user-select: none;
  overflow: hidden;
}

.menu-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.menu-item {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 14px;
  height: 32px;
  cursor: pointer;
  color: #1D2129;
  transition: background 0.12s ease, color 0.12s ease;
  white-space: nowrap;
  margin: 0 6px;
  border-radius: 6px;
}

.menu-item:hover,
.menu-item.menu-active {
  background: rgba(43, 90, 237, 0.08);
  color: #2B5AED;
}

.menu-item.menu-danger {
  color: #F53F3F;
}

.menu-item.menu-danger:hover {
  background: rgba(245, 63, 63, 0.08);
  color: #F53F3F;
}

.menu-item.menu-disabled {
  color: #C9CDD4;
  cursor: not-allowed;
}

.menu-item.menu-disabled:hover {
  background: transparent;
  color: #C9CDD4;
}

.menu-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 400;
}

.menu-arrow {
  font-size: 8px;
  color: #86909C;
  flex-shrink: 0;
  transform: scale(0.75);
  opacity: 0.7;
  transition: opacity 0.12s;
}

.menu-item:hover .menu-arrow,
.menu-item.menu-active .menu-arrow {
  opacity: 1;
  color: #2B5AED;
}

.menu-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, rgba(0,0,0,0.06) 10%, rgba(0,0,0,0.06) 90%, transparent 100%);
  margin: 5px 12px;
  list-style: none;
}

/* 子菜单 */
.menu-submenu {
  position: absolute;
  left: calc(100% - 6px);
  top: -6px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px) saturate(1.8);
  -webkit-backdrop-filter: blur(20px) saturate(1.8);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.04),
    0 4px 8px rgba(0, 0, 0, 0.04),
    0 12px 24px rgba(0, 0, 0, 0.08),
    0 24px 48px rgba(0, 0, 0, 0.06);
  padding: 6px 0;
  min-width: 160px;
  z-index: 10000;
  overflow: hidden;
}

.menu-nested .menu-item {
  height: 30px;
  font-size: 12px;
  padding: 0 12px;
  margin: 0 6px;
}

/* 动画 */
.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.12s ease, transform 0.12s ease;
}

.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: scale(0.97);
}

.menu-fade-enter-to,
.menu-fade-leave-from {
  opacity: 1;
  transform: scale(1);
}
</style>
