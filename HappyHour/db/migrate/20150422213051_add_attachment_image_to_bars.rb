class AddAttachmentImageToBars < ActiveRecord::Migration
  def self.up
    change_table :bars do |t|
      t.attachment :image
    end
  end

  def self.down
    remove_attachment :bars, :image
  end
end
