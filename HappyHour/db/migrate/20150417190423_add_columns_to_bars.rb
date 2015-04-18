class AddColumnsToBars < ActiveRecord::Migration
  def change
    add_column :bars, :time, :string
    add_column :bars, :image, :string
    add_column :bars, :description, :text
  end
end
